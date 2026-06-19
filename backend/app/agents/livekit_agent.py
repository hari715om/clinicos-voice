"""
ClinicOS Voice — LiveKit Voice Agent (livekit-agents v1.6+ API)

Architecture:
  Agent subclass + AgentSession (v1.6):
    STT  -> Deepgram Nova-2-General   (fast, accurate, Indian English)
    LLM  -> Groq llama-3.3-70b        (sub-1s inference, function calling)
    TTS  -> ElevenLabs Matilda         (professional voice, free tier)
    VAD  -> Silero (bundled default)   (accurate voice activity detection)

Run from backend/ with venv active:
    python -m app.agents.livekit_agent dev
"""
from __future__ import annotations

# ── Monkey-patch for livekit-agents v1.6.1 Pydantic v2 serialization bug ──────
#
# ROOT CAUSE:
#   Instructions is a str subclass. In ChatContent = ... | Instructions | str,
#   Pydantic v2's union serializer calls Instructions.serialize(v) for ALL
#   string values (plain str + Instructions subclass), because it can't reliably
#   distinguish them during serialization phase.
#
#   When v is a plain str (e.g. assistant/user messages), v.audio raises
#   AttributeError → PydanticSerializationError → entire _llm_inference_task fails
#   → agent crashes after every user turn.
#
# FIX:
#   Patch Instructions.__get_pydantic_core_schema__ BEFORE any Pydantic models
#   are compiled so the serialize function gracefully handles plain strings.
#
# ─────────────────────────────────────────────────────────────────────────────
def _patch_instructions_serializer() -> None:
    """
    Fix livekit-agents v1.6.1 Pydantic v2 serialization bug.

    Root cause:
      Instructions is a str subclass. Pydantic v2's union serializer calls
      Instructions.serialize(v) for ALL string values (not just Instructions
      instances), so plain str values fail with AttributeError: 'str'.has.no'.audio'.

    Fix:
      1. Patch Instructions.__get_pydantic_core_schema__ with a serializer that
         handles plain str gracefully.
      2. Force-rebuild all Pydantic models that were compiled using the old schema
         (AgentConfigUpdate, ChatMessage, etc.) so they pick up the new serializer.
    """
    from livekit.agents.llm.chat_context import (
        AgentConfigUpdate, AgentHandoff, ChatMessage,
        FunctionCall, FunctionCallOutput, Instructions,
    )
    from pydantic_core import core_schema

    @classmethod  # type: ignore[misc]
    def _patched_schema(cls, source_type, handler):  # type: ignore[override]
        def validate_python(v):
            if isinstance(v, Instructions):
                return v
            if isinstance(v, dict) and v.get("type") == "instructions":
                return cls(v["audio"], text=v.get("text"))
            raise ValueError(f"Cannot convert {type(v)!r} to Instructions")

        def validate_json(v):
            if isinstance(v, dict) and v.get("type") == "instructions":
                return cls(v["audio"], text=v.get("text"))
            raise ValueError(f"Cannot convert {type(v)!r} to Instructions")

        def serialize(v):
            # Guard: Pydantic v2 calls this for ALL str values in the union,
            # not just Instructions instances. Handle plain str gracefully.
            if not isinstance(v, Instructions):
                return str(v)
            d = {"type": "instructions", "audio": v.audio}
            if v._text_variant is not None:
                d["text"] = v._text_variant
            return d

        return core_schema.json_or_python_schema(
            python_schema=core_schema.no_info_plain_validator_function(validate_python),
            json_schema=core_schema.no_info_plain_validator_function(validate_json),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize, info_arg=False
            ),
        )

    # Apply the patch
    Instructions.__get_pydantic_core_schema__ = _patched_schema  # type: ignore[assignment]

    # Force-rebuild every model that references Instructions so their compiled
    # Pydantic core schemas use the new serializer (models compile at import time
    # before the patch, so they'd still use the old broken serializer otherwise).
    for _model in (AgentConfigUpdate, ChatMessage, FunctionCall, FunctionCallOutput, AgentHandoff):
        _model.model_rebuild(force=True)


# Apply the patch immediately — before livekit model schemas are built
_patch_instructions_serializer()
# ──────────────────────────────────────────────────────────────────────────────

from typing import AsyncGenerator
import itertools, re as _re


class _FuncTagFilter:
    """Strip <function=...>...</function> from a streamed LLM text without blocking tool calls.

    The model sometimes echoes function calls as plain text (e.g.:
    'Let me check... <function=check_availability>{...}</function>').
    This filter removes those tags before text reaches TTS while the actual
    structured tool calls (handled by livekit) pass through unaffected.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_tag = False

    def feed(self, text: str) -> str:
        """Feed a streaming chunk; return safe text to emit."""
        self._buf += text
        result = ""
        while True:
            if self._in_tag:
                end = self._buf.find("</function>")
                if end == -1:
                    return result  # still inside tag, buffer everything
                self._buf = self._buf[end + 11:]  # skip </function>
                self._in_tag = False
            else:
                start = self._buf.find("<function=")
                if start == -1:
                    # No tag — emit all but last 10 chars (guard partial tag boundary)
                    cutoff = max(0, len(self._buf) - 10)
                    result += self._buf[:cutoff]
                    self._buf = self._buf[cutoff:]
                    return result
                result += self._buf[:start]
                self._buf = self._buf[start:]
                self._in_tag = True

    def flush(self) -> str:
        """Flush remaining safe content at end of stream."""
        if not self._in_tag:
            out = self._buf
            self._buf = ""
            return out
        return ""


from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    ModelSettings,
    WorkerOptions,
    cli,
    llm,
)
# ALL plugin imports MUST be at module level (main-thread plugin registration)
from livekit.plugins import deepgram, elevenlabs
from livekit.plugins import groq as groq_plugin

from app.agents.prompt_templates import build_system_prompt
from app.agents.tool_definitions import ALL_TOOLS
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def _validate_config() -> bool:
    """Validate all required credentials before starting."""
    missing = []
    if not settings.LIVEKIT_URL:
        missing.append("LIVEKIT_URL")
    if not settings.LIVEKIT_API_KEY:
        missing.append("LIVEKIT_API_KEY")
    if not settings.LIVEKIT_API_SECRET:
        missing.append("LIVEKIT_API_SECRET")
    if not settings.GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        logger.error(
            "missing_credentials",
            missing=missing,
            detail="Set these in backend/.env before starting the agent",
        )
        return False
    return True


# ── Agent ─────────────────────────────────────────────────────────────────────

class ClinicVoiceAgent(Agent):
    """
    ClinicOS AI receptionist (Aria).

    The real system prompt is injected in llm_node (Groq-compatible role='system').
    Agent.instructions uses a plain placeholder so the patched serializer has
    minimal work to do.

    Overrides:
      on_enter  — sends the opening greeting when session starts
      llm_node  — strips placeholder system msg and injects real system prompt
    """

    def __init__(self, system_prompt: str) -> None:
        super().__init__(
            instructions=" ",  # placeholder; real prompt injected in llm_node
            tools=ALL_TOOLS,
        )
        self._system_prompt = system_prompt

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def on_enter(self) -> None:
        """Called automatically when agent joins the session. Send greeting."""
        logger.info("agent_ready")
        await self.session.say(
            "Good morning, thank you for calling Utkal Hospital. "
            "My name is Aria, your AI receptionist. "
            "How may I assist you today?",
            allow_interruptions=True,
        )

    # ── LLM pipeline override ─────────────────────────────────────────────────

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list,
        model_settings: ModelSettings,
    ) -> AsyncGenerator[llm.ChatChunk, None]:
        """
        Inject real system prompt and strip livekit-internal items before Groq.

        chat_ctx contents at call time:
          - AgentConfigUpdate (internal instructions config)
          - ChatMessage(role='system', content=[' '])  — placeholder from init
          - ChatMessage(role='assistant', ...)          — previous turns
          - ChatMessage(role='user', ...)               — current user input

        We replace all of that with a clean context starting with our real prompt.
        """
        fixed_ctx = llm.ChatContext()

        # 1. Real system prompt first (Groq-compatible role='system' message)
        fixed_ctx.add_message(role="system", content=self._system_prompt)

        # 2. Copy conversation turns only:
        #    skip agent_config_update (internal livekit type, not supported by Groq)
        #    skip system/developer messages (replaced by our real prompt above)
        conv_items = []
        for item in chat_ctx.items:
            item_type = getattr(item, "type", None)
            item_role = getattr(item, "role", None)
            if item_type == "agent_config_update":
                continue
            if item_type == "message" and item_role in ("system", "developer"):
                continue
            conv_items.append(item)

        # Truncate to last 20 items (10 turns) to stay within Groq's TPM limit.
        # Appointment booking needs ~10 turns; 12 was too aggressive and caused
        # the model to hallucinate slot UUIDs when check_availability results
        # were truncated out before book_appointment was called.
        MAX_CONTEXT_ITEMS = 20
        if len(conv_items) > MAX_CONTEXT_ITEMS:
            logger.debug(
                "context_truncated",
                original=len(conv_items),
                kept=MAX_CONTEXT_ITEMS,
            )
        fixed_ctx.items.extend(conv_items[-MAX_CONTEXT_ITEMS:])

        # Stream with function-tag filter: strips <function=...>...</function>
        # from text chunks before they reach TTS, while keeping actual tool calls.
        tag_filter = _FuncTagFilter()
        async for chunk in super().llm_node(fixed_ctx, tools, model_settings):
            if chunk.delta and chunk.delta.content:
                cleaned = tag_filter.feed(chunk.delta.content)
                chunk.delta.content = cleaned if cleaned else None
            yield chunk


# ── Entrypoint ────────────────────────────────────────────────────────────────

async def entrypoint(ctx: JobContext) -> None:
    """Called once per incoming voice call by the LiveKit worker."""
    logger.info("agent_job_started", room=ctx.room.name, model=settings.GROQ_MODEL)

    # Connect to the LiveKit room first
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Fetch live clinic data for a dynamic system prompt
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as http:
            r = await http.get(
                f"http://localhost:8000/api/v1/clinics/{settings.CLINIC_ID}"
            )
            clinic_data = r.json() if r.status_code == 200 else {}
    except Exception:
        clinic_data = {}

    system_prompt = build_system_prompt(
        clinic_name=clinic_data.get("name", "Utkal Hospital"),
        clinic_city=clinic_data.get("city", "Bhubaneswar"),
        departments=[d.get("name", "") for d in clinic_data.get("departments", [])],
        doctors=[d.get("name", "") for d in clinic_data.get("doctors", [])],
    )

    # ── Plugins ───────────────────────────────────────────────────────────────
    stt = deepgram.STT(
        model="nova-2-general",
        language="en-IN",        # Indian English accent
        api_key=getattr(settings, "DEEPGRAM_API_KEY", None),
    )

    # ── Groq LLM with API key rotation ───────────────────────────────────────
    # Round-robin across all GROQ_API_KEYS to spread TPM usage.
    # With multiple free-tier accounts this avoids per-key rate limits.
    groq_keys = settings.groq_keys()
    if not groq_keys:
        raise RuntimeError("No Groq API key configured in GROQ_API_KEY / GROQ_API_KEYS")

    # Build one LLM client per key
    _llm_pool = [
        groq_plugin.LLM(model=settings.GROQ_MODEL, api_key=k)
        for k in groq_keys
    ]
    _llm_cycle = itertools.cycle(_llm_pool)
    groq_llm = next(_llm_cycle)  # start with the first key

    logger.info(
        "groq_pool_ready",
        model=settings.GROQ_MODEL,
        num_keys=len(groq_keys),
    )

    tts = elevenlabs.TTS(
        voice_id="XrExE9yKIg1WjnnlVkGX",   # Matilda – Professional (free tier ✅)
        model="eleven_turbo_v2_5",
        api_key=getattr(settings, "ELEVENLABS_API_KEY", None),
        language="en",
    )

    # ── Build and start the session ───────────────────────────────────────────
    agent = ClinicVoiceAgent(system_prompt=system_prompt)

    # vad= intentionally omitted — AgentSession v1.6 uses bundled Silero by default
    session = AgentSession(
        stt=stt,
        llm=groq_llm,
        tts=tts,
    )

    # on_enter() fires the greeting automatically after session.start() returns
    await session.start(agent=agent, room=ctx.room)


# ── Worker entry ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _validate_config():
        raise SystemExit(1)

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            ws_url=settings.LIVEKIT_URL,
        )
    )
