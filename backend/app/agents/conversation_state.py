"""
Conversation State — tracks the agent's in-memory understanding of a call.

This dataclass is the agent's scratchpad. It is updated as the patient provides
information and as tool calls return results. It allows the agent to:
- Accumulate partial information across multiple turns
- Branch when the user changes their mind
- Avoid re-asking for information already provided
- Prevent hallucination (nothing is assumed — everything must be confirmed by a tool call)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.core.constants import AgentIntent


@dataclass
class ConversationContext:
    """
    In-memory state for a single voice agent conversation.

    Updated by tool results and user utterances.
    Reset to a new instance at the start of each call.
    """

    # ── Session ────────────────────────────────────────────────────────────────
    call_session_id: Optional[uuid.UUID] = None
    clinic_id: Optional[uuid.UUID] = None

    # ── Patient info (collected from caller) ──────────────────────────────────
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_id: Optional[uuid.UUID] = None  # Populated after first backend lookup

    # ── Intent ────────────────────────────────────────────────────────────────
    current_intent: AgentIntent = AgentIntent.UNKNOWN
    previous_intent: Optional[AgentIntent] = None  # Useful for mid-conversation changes

    # ── Booking context ───────────────────────────────────────────────────────
    department_name: Optional[str] = None
    doctor_id: Optional[uuid.UUID] = None
    doctor_name: Optional[str] = None
    preferred_date: Optional[str] = None        # YYYY-MM-DD
    preferred_time_hint: Optional[str] = None   # "morning", "afternoon", "10am"
    appointment_type: Optional[str] = None
    reason: Optional[str] = None

    # ── Slot selection ────────────────────────────────────────────────────────
    offered_slots: list[dict] = field(default_factory=list)  # Slots presented to patient
    selected_slot_id: Optional[uuid.UUID] = None

    # ── Existing appointment (for reschedule/cancel) ──────────────────────────
    existing_appointment_id: Optional[uuid.UUID] = None
    existing_appointments: list[dict] = field(default_factory=list)

    # ── Confirmation state ────────────────────────────────────────────────────
    pending_confirmation: bool = False  # True when agent is awaiting yes/no
    confirmed: bool = False             # True after patient explicitly confirmed

    # ── Turn tracking ─────────────────────────────────────────────────────────
    turn_count: int = 0
    clarification_count: int = 0

    def reset_booking_context(self) -> None:
        """Clear booking-specific state when intent changes mid-conversation."""
        self.department_name = None
        self.doctor_id = None
        self.doctor_name = None
        self.preferred_date = None
        self.preferred_time_hint = None
        self.appointment_type = None
        self.reason = None
        self.offered_slots = []
        self.selected_slot_id = None
        self.pending_confirmation = False
        self.confirmed = False

    def switch_intent(self, new_intent: AgentIntent) -> None:
        """Handle mid-conversation intent change cleanly."""
        self.previous_intent = self.current_intent
        self.current_intent = new_intent
        self.reset_booking_context()

    def missing_booking_fields(self) -> list[str]:
        """Return names of required booking fields not yet collected."""
        missing = []
        if not self.patient_name:
            missing.append("patient_name")
        if not self.patient_phone:
            missing.append("phone_number")
        if not self.doctor_id and not self.department_name:
            missing.append("doctor_or_department")
        if not self.preferred_date:
            missing.append("preferred_date")
        if not self.appointment_type:
            missing.append("appointment_type")
        return missing

    def is_ready_to_book(self) -> bool:
        """Return True if all required booking fields are collected and a slot is selected."""
        return (
            bool(self.patient_name)
            and bool(self.patient_phone)
            and bool(self.selected_slot_id)
            and bool(self.appointment_type)
        )
