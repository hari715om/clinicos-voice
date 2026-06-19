"""
Tool definitions for the ClinicOS Voice agent — livekit-agents v1.6+ API.

Uses @function_tool decorator (replaces old @llm.ai_callable + FunctionContext).
All tools make HTTP calls to the FastAPI backend.
"""
from __future__ import annotations

from typing import Annotated, Optional

import httpx

import re
from datetime import date, datetime, timedelta

from livekit.agents import function_tool, RunContext

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

BACKEND_BASE = "http://localhost:8000/api/v1"


# ── Date parsing ─────────────────────────────────────────────────────────────

def parse_date_smart(date_str: str) -> str:
    """
    Convert any natural language date string to YYYY-MM-DD.

    Handles:
      - YYYY-MM-DD already formatted            → pass through
      - 'today', 'tomorrow', 'day after tomorrow'
      - Ordinal month formats: '25th June', 'June 19th', '19th June 2026'
      - Relative: 'next Monday', 'this Friday'
      - dateutil fallback for everything else
    """
    s = date_str.strip().lower()
    today = date.today()

    # Already ISO format — but still check if it's in the past
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        try:
            d = datetime.strptime(s, '%Y-%m-%d').date()
            if d < today:
                # Push to same day/month this year, or next year if still past
                d = d.replace(year=today.year)
                if d < today:
                    d = d.replace(year=today.year + 1)
            return d.strftime('%Y-%m-%d')
        except ValueError:
            pass  # fall through to dateutil

    # Simple relative keywords
    if s in ('today', 'now', 'today\'s date'):
        return today.strftime('%Y-%m-%d')
    if s in ('tomorrow', 'tmrw', 'tmr'):
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    if s in ('day after tomorrow', 'day after tmr'):
        return (today + timedelta(days=2)).strftime('%Y-%m-%d')

    # Strip ordinal suffixes: '25th' → '25', '1st' → '1'
    s_clean = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', date_str.strip())

    try:
        from dateutil import parser as du
        from dateutil.relativedelta import relativedelta
        parsed = du.parse(
            s_clean,
            dayfirst=True,
            default=datetime(today.year, today.month, 1),
        ).date()
        # If the parsed date is in the past, push to next year
        if parsed < today:
            parsed = parsed.replace(year=today.year + 1)
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        pass

    # Last resort: try direct strptime
    for fmt in ('%d %B %Y', '%d %B', '%B %d %Y', '%B %d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            d = datetime.strptime(s_clean, fmt)
            if d.year == 1900:
                d = d.replace(year=today.year)
                if d.date() < today:
                    d = d.replace(year=today.year + 1)
            return d.strftime('%Y-%m-%d')
        except ValueError:
            continue

    # Give up gracefully — return original; the API will give a useful error
    return date_str


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get(endpoint: str, params: dict | None = None) -> dict | list:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BACKEND_BASE}{endpoint}", params=params)
        r.raise_for_status()
        return r.json()


async def _post(endpoint: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{BACKEND_BASE}{endpoint}", json=body)
        r.raise_for_status()
        return r.json()


async def _patch(endpoint: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.patch(f"{BACKEND_BASE}{endpoint}", json=body)
        r.raise_for_status()
        return r.json()


async def _delete(endpoint: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(f"{BACKEND_BASE}{endpoint}", json=body or {})
        r.raise_for_status()
        return r.json()


# ── Tool definitions ──────────────────────────────────────────────────────────

@function_tool
async def get_doctor_list(
    context: RunContext,
    department: Annotated[str, "The medical department name, e.g. 'Cardiology', 'Neurology'"],
) -> str:
    """List available doctors in a department. Call this when the patient mentions a department but not a specific doctor."""
    clinic_id = settings.CLINIC_ID
    try:
        result = await _get(f"/clinics/{clinic_id}/doctors", params={"department_name": department})
        if not result:
            return f"No doctors found for {department}."
        doctors = result if isinstance(result, list) else []
        lines = [f"- Dr. {d['name']} (ID: {d['id']})" for d in doctors[:5]]
        return f"Available doctors in {department}:\n" + "\n".join(lines)
    except Exception as e:
        logger.error("get_doctor_list_failed", error=str(e))
        return f"Could not retrieve doctors for {department} at this time."


@function_tool
async def check_availability(
    context: RunContext,
    date: Annotated[str, "Date in YYYY-MM-DD format. Convert relative dates (e.g. 'tomorrow') to exact dates first."],
    doctor_name: Annotated[Optional[str], "Optional doctor name to filter by"] = None,
    department: Annotated[Optional[str], "Optional department name to filter by"] = None,
) -> str:
    """Check available appointment slots for a given date. ALWAYS call this before suggesting any slot to a patient. Returns slot_id and doctor_id UUIDs that must be used in book_appointment."""
    # Convert any natural language date to YYYY-MM-DD (e.g. '25th June' → '2026-06-25')
    parsed_date = parse_date_smart(date)
    if parsed_date != date:
        logger.info("date_normalised", original=date, parsed=parsed_date)
    params: dict = {"clinic_id": settings.CLINIC_ID, "date": parsed_date}
    if doctor_name:
        params["doctor_name"] = doctor_name
    if department:
        params["department"] = department
    try:
        result = await _get("/availability", params=params)
        slots = result.get("available_slots", []) if isinstance(result, dict) else []
        if not slots:
            alt = result.get("nearest_alternatives", []) if isinstance(result, dict) else []
            base = f"No slots on {parsed_date}"
            if doctor_name or department:
                base += f" for {doctor_name or department}"
            if alt:
                alt_dates = ", ".join(set(s.get("start_time", "")[:10] for s in alt[:3]))
                base += f". Try these dates: {alt_dates}"
            return base + "."

        # Structured format — UUIDs on their own lines so the model can copy them exactly
        lines = [f"Available slots on {parsed_date}:"]
        for i, s in enumerate(slots[:6], 1):
            time_str = s.get("start_time", "")[:16].replace("T", " ")
            dr = s.get("doctor_name", "")
            dept = s.get("department_name", "")
            sid = s.get("slot_id", "")
            did = s.get("doctor_id", "")
            lines.append(
                f"Slot {i}: {time_str} | {dr} ({dept})\n"
                f"  slot_id: {sid}\n"
                f"  doctor_id: {did}"
            )
        lines.append("Use the exact slot_id and doctor_id above in book_appointment.")
        return "\n".join(lines)
    except Exception as e:
        logger.error("check_availability_failed", error=str(e))
        return f"Could not check availability for {parsed_date}. Please try another date."


@function_tool
async def book_appointment(
    context: RunContext,
    patient_name: Annotated[str, "Full name of the patient"],
    phone_number: Annotated[str, "10-digit phone number"],
    doctor_id: Annotated[str, "UUID of the doctor from check_availability result"],
    slot_id: Annotated[str, "UUID of the slot from check_availability result"],
    appointment_type: Annotated[str, "One of: new_consultation, follow_up, review, emergency"],
    reason: Annotated[Optional[str], "Optional short reason for the visit"] = None,
) -> str:
    """Book a confirmed appointment. ONLY call after: (1) check_availability returned slot_id + doctor_id UUIDs, (2) patient gave their name and phone, (3) patient verbally confirmed the slot."""
    import re as _re
    _UUID = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.I)
    if not _UUID.match(slot_id):
        return (
            "ERROR: slot_id must be the UUID from check_availability (e.g. 'a1b2c3d4-...'). "
            "You passed a time string. Call check_availability first and use the slot_id value from the result."
        )
    if not _UUID.match(doctor_id):
        return (
            "ERROR: doctor_id must be the UUID from check_availability. "
            "You passed an invalid value. Call check_availability first."
        )
    if patient_name in ("", "<patient_name>", "unknown") or phone_number in ("", "<phone_number>", "unknown"):
        return "ERROR: Must collect patient's real name and 10-digit phone number before booking."

    # Normalize appointment_type: accept natural language and map to API values
    _APPT_TYPE_MAP = {
        "new_consultation": "new_consultation",
        "new consultation": "new_consultation",
        "new": "new_consultation",
        "first": "new_consultation",
        "first visit": "new_consultation",
        "first consultation": "new_consultation",
        "regular consultation": "new_consultation",
        "regular": "new_consultation",
        "follow_up": "follow_up",
        "follow up": "follow_up",
        "followup": "follow_up",
        "returning": "follow_up",
        "review": "review",
        "emergency": "emergency",
        "urgent": "emergency",
    }
    appointment_type = _APPT_TYPE_MAP.get(appointment_type.strip().lower(), "new_consultation")

    try:
        result = await _post("/appointments", {
            "clinic_id": settings.CLINIC_ID,
            "patient_name": patient_name,
            "phone_number": phone_number,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
            "appointment_type": appointment_type,
            "reason": reason,
            "booking_source": "voice_agent",
        })
        appt_id = result.get("id", "")
        slot_time = result.get("slot_start_time", "")[:16].replace("T", " ") if result.get("slot_start_time") else ""
        return (
            f"Appointment confirmed for {patient_name}. "
            f"Appointment ID: {appt_id}. "
            f"Slot: {slot_time}. "
            "The patient will receive a confirmation."
        )
    except Exception as e:
        logger.error("book_appointment_failed", error=str(e))
        return f"Sorry, the booking failed: {str(e)}. Please try again or choose a different slot."


@function_tool
async def lookup_patient_appointments(
    context: RunContext,
    phone_number: Annotated[str, "10-digit phone number of the patient"],
) -> str:
    """Look up existing appointments for a patient by phone number. Call this at the start of reschedule or cancel flows."""
    try:
        result = await _get(f"/patients/{phone_number}/appointments", params={"active_only": "true"})
        appts = result if isinstance(result, list) else []
        if not appts:
            return f"No active appointments found for phone number {phone_number}."
        lines = []
        for a in appts[:4]:
            aid = a.get("id", "")
            dr = a.get("doctor_name", "")
            slot = (a.get("slot_start_time") or "")[:16].replace("T", " ")
            status = a.get("status", "")
            lines.append(f"- ID: {aid} | {dr} | {slot} | {status}")
        return f"Appointments for {phone_number}:\n" + "\n".join(lines)
    except Exception as e:
        logger.error("lookup_appointments_failed", error=str(e))
        return f"Could not find appointments for {phone_number}."


@function_tool
async def reschedule_appointment(
    context: RunContext,
    appointment_id: Annotated[str, "UUID of the appointment to reschedule"],
    new_slot_id: Annotated[str, "UUID of the new slot from check_availability"],
    reason: Annotated[Optional[str], "Reason for rescheduling"] = None,
) -> str:
    """Reschedule an existing appointment to a new slot."""
    try:
        result = await _patch(f"/appointments/{appointment_id}", {
            "new_slot_id": new_slot_id,
            "reason": reason,
        })
        slot_time = result.get("slot_start_time", "")[:16].replace("T", " ") if result.get("slot_start_time") else ""
        return f"Appointment rescheduled successfully. New slot: {slot_time}."
    except Exception as e:
        logger.error("reschedule_failed", error=str(e))
        return f"Rescheduling failed: {str(e)}."


@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: Annotated[str, "UUID of the appointment to cancel"],
    reason: Annotated[Optional[str], "Reason for cancellation"] = None,
) -> str:
    """Cancel an existing appointment. The slot is immediately freed."""
    try:
        await _delete(f"/appointments/{appointment_id}", {"reason": reason})
        return "Appointment has been successfully cancelled. The slot is now free."
    except Exception as e:
        logger.error("cancel_failed", error=str(e))
        return f"Cancellation failed: {str(e)}."


# Expose all tools as a list for easy import into the agent
ALL_TOOLS = [
    get_doctor_list,
    check_availability,
    book_appointment,
    lookup_patient_appointments,
    reschedule_appointment,
    cancel_appointment,
]
