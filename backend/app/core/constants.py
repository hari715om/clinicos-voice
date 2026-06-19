"""
Enumeration constants used throughout ClinicOS Voice.
Keep all domain string literals here to avoid typos and enable IDE completion.
"""
from __future__ import annotations

from enum import Enum


class SlotStatus(str, Enum):
    """Lifecycle state of a single doctor slot."""

    AVAILABLE = "available"
    HELD = "held"        # Temporarily reserved during booking flow (expires after SLOT_HOLD_SECONDS)
    BOOKED = "booked"    # Committed — linked to an active appointment
    BLOCKED = "blocked"  # Manually blocked (lunch break, holiday, admin action)


class AppointmentStatus(str, Enum):
    """Lifecycle state of a patient appointment."""

    BOOKED = "booked"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class BookingSource(str, Enum):
    """Origin of the booking action — used for analytics."""

    VOICE_AGENT = "voice_agent"
    MANUAL = "manual"
    WEB = "web"
    ADMIN = "admin"


class CallStatus(str, Enum):
    """State of a live voice call session."""

    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"
    ABANDONED = "abandoned"


class AgentIntent(str, Enum):
    """Patient intent detected by the voice receptionist agent."""

    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    CHECK_AVAILABILITY = "check_availability"
    LOOKUP_APPOINTMENT = "lookup_appointment"
    UNKNOWN = "unknown"


class CallEventType(str, Enum):
    """Granular event types emitted during a call session."""

    SESSION_STARTED = "session_started"
    INTENT_DETECTED = "intent_detected"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT_RECEIVED = "tool_result_received"
    SLOT_SUGGESTED = "slot_suggested"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_FAILED = "appointment_failed"
    CLARIFICATION_REQUESTED = "clarification_requested"
    INTENT_CHANGED = "intent_changed"
    SESSION_ENDED = "session_ended"
    ERROR = "error"


class DayOfWeek(int, Enum):
    """Day-of-week mapping — matches Python's `datetime.weekday()` (0 = Monday)."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


# Human-readable names for days — indexed by DayOfWeek value
DAY_NAMES: dict[int, str] = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}
