"""Verify the Instructions monkey-patch works for all serialization cases."""
from app.agents.livekit_agent import ClinicVoiceAgent, _validate_config
from app.agents.tool_definitions import ALL_TOOLS
from livekit.agents.llm.chat_context import (
    ChatMessage, AgentConfigUpdate, Instructions, ChatContext
)

# Test 1: ChatMessage with plain str content
msg = ChatMessage(role="system", content=[" "])
dumped = msg.model_dump(mode="json")
assert dumped["content"] == [" "], f"Got {dumped['content']}"
print("PASS: ChatMessage(plain str).model_dump() works")

# Test 2: ChatMessage with Instructions content
inst = Instructions("You are Aria.")
msg2 = ChatMessage(role="assistant", content=[inst])
dumped2 = msg2.model_dump(mode="json")
assert dumped2["content"][0]["type"] == "instructions"
assert dumped2["content"][0]["audio"] == "You are Aria."
print("PASS: ChatMessage(Instructions).model_dump() works")

# Test 3: AgentConfigUpdate with plain str
cfg = AgentConfigUpdate(instructions=" ")
dumped3 = cfg.model_dump(mode="json", exclude_none=True)
print(f"PASS: AgentConfigUpdate.model_dump() works: instructions={dumped3.get('instructions')}")

# Test 4: Full ChatContext.to_dict()
ctx = ChatContext()
ctx.items.append(ChatMessage(role="system", content=[" "]))
ctx.items.append(ChatMessage(role="assistant", content=["Good morning!"]))
ctx.items.append(ChatMessage(role="user", content=["Book an appointment"]))
result = ctx.to_dict()
print(f"PASS: ChatContext.to_dict() works, {len(result['items'])} items")

print()
print(f"Config: {_validate_config()} | Tools: {len(ALL_TOOLS)}")
print("ALL CHECKS PASSED - agent ready to start")
