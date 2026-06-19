"""
Availability Service.

Queries available slots for a doctor on a given date.
Handles expiry of held slots and suggests nearest alternatives when
the requested date has no open slots.

This is the service the voice agent calls before suggesting any time to a patient.
The agent MUST NOT invent availability — it MUST call this service.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SlotStatus
from app.core.exceptions import DoctorNotFoundError, InvalidDateError
from app.core.logging import get_logger
from app.models.doctor import Doctor
from app.models.slot import DoctorSlot
from app.utils.time_utils import now_utc, parse_date, ist_datetime, to_utc
import pytz

logger = get_logger(__name__)
IST = pytz.timezone("Asia/Kolkata")


async def _expire_held_slots(db: AsyncSession) -> int:
    """
    Release any HELD slots whose hold_expires_at timestamp has passed.
    Called at the start of availability queries to prevent stale holds.
    Returns the count of slots released.
    """
    now = now_utc()
    result = await db.execute(
        update(DoctorSlot)
        .where(
            and_(
                DoctorSlot.slot_status == SlotStatus.HELD,
                DoctorSlot.hold_expires_at <= now,
            )
        )
        .values(slot_status=SlotStatus.AVAILABLE, hold_expires_at=None)
        .returning(DoctorSlot.id)
    )
    released = len(result.fetchall())
    if released:
        logger.info("held_slots_released", count=released)
    return released


async def get_available_slots(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    target_date: str,  # YYYY-MM-DD
    doctor_id: Optional[uuid.UUID] = None,
    department_id: Optional[uuid.UUID] = None,
) -> list[DoctorSlot]:
    """
    Return all AVAILABLE slots for a clinic on a specific date.
    Optionally filtered by doctor or department.

    Steps:
    1. Expire stale holds.
    2. Parse and validate the date.
    3. Query slots within the day boundary (IST midnight → IST midnight+1).
    4. Optionally filter by doctor_id or department.
    """
    await _expire_held_slots(db)

    # Parse the date
    try:
        d = parse_date(target_date)
    except ValueError:
        raise InvalidDateError(f"Invalid date format: {target_date!r}. Expected YYYY-MM-DD.")

    # Build IST day boundaries → convert to UTC for DB query
    day_start_ist = IST.localize(datetime.combine(d, datetime.min.time()))
    day_end_ist = day_start_ist + timedelta(days=1)
    day_start_utc = day_start_ist.astimezone(pytz.UTC)
    day_end_utc = day_end_ist.astimezone(pytz.UTC)

    # Base filter
    filters = [
        DoctorSlot.clinic_id == clinic_id,
        DoctorSlot.slot_status == SlotStatus.AVAILABLE,
        DoctorSlot.start_time >= day_start_utc,
        DoctorSlot.start_time < day_end_utc,
    ]

    if doctor_id:
        filters.append(DoctorSlot.doctor_id == doctor_id)

    if department_id:
        # Join through Doctor to filter by department
        stmt = (
            select(DoctorSlot)
            .join(Doctor, DoctorSlot.doctor_id == Doctor.id)
            .where(and_(*filters, Doctor.department_id == department_id))
            .order_by(DoctorSlot.start_time)
        )
    else:
        stmt = (
            select(DoctorSlot)
            .where(and_(*filters))
            .order_by(DoctorSlot.start_time)
        )

    result = await db.execute(stmt)
    slots = list(result.scalars().all())

    logger.info(
        "availability_queried",
        clinic_id=str(clinic_id),
        date=target_date,
        doctor_id=str(doctor_id) if doctor_id else None,
        available_count=len(slots),
    )
    return slots


async def find_nearest_alternatives(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    doctor_id: uuid.UUID,
    from_date: str,
    n: int = 3,
    search_days: int = 14,
) -> list[DoctorSlot]:
    """
    Find the next N available slots for a doctor starting from `from_date`.
    Used when the patient's preferred date has no availability.
    """
    await _expire_held_slots(db)

    try:
        start = parse_date(from_date)
    except ValueError:
        raise InvalidDateError(f"Invalid date: {from_date!r}")

    from_ist = IST.localize(datetime.combine(start, datetime.min.time()))
    from_utc = from_ist.astimezone(pytz.UTC)
    until_utc = from_utc + timedelta(days=search_days)

    stmt = (
        select(DoctorSlot)
        .where(
            and_(
                DoctorSlot.clinic_id == clinic_id,
                DoctorSlot.doctor_id == doctor_id,
                DoctorSlot.slot_status == SlotStatus.AVAILABLE,
                DoctorSlot.start_time >= from_utc,
                DoctorSlot.start_time < until_utc,
            )
        )
        .order_by(DoctorSlot.start_time)
        .limit(n)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def hold_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    hold_seconds: int = 300,
) -> DoctorSlot:
    """
    Attempt to place a temporary hold on a slot (SELECT FOR UPDATE → set HELD).
    Returns the slot if successful.
    Raises SlotNotAvailableError if the slot is not in AVAILABLE state.
    """
    from app.core.exceptions import SlotNotAvailableError, SlotNotFoundError

    # Lock the row
    stmt = (
        select(DoctorSlot)
        .where(DoctorSlot.id == slot_id)
        .with_for_update(skip_locked=False)
    )
    result = await db.execute(stmt)
    slot = result.scalar_one_or_none()

    if slot is None:
        raise SlotNotFoundError(f"Slot {slot_id} not found.")

    if slot.slot_status != SlotStatus.AVAILABLE:
        raise SlotNotAvailableError(
            f"Slot {slot_id} is not available (current status: {slot.slot_status})."
        )

    slot.slot_status = SlotStatus.HELD
    slot.hold_expires_at = now_utc() + timedelta(seconds=hold_seconds)
    await db.flush()

    logger.info("slot_held", slot_id=str(slot_id), expires_in_seconds=hold_seconds)
    return slot


async def release_slot(db: AsyncSession, slot_id: uuid.UUID) -> None:
    """Release a slot back to AVAILABLE (used on cancellation/reschedule)."""
    stmt = (
        update(DoctorSlot)
        .where(DoctorSlot.id == slot_id)
        .values(slot_status=SlotStatus.AVAILABLE, hold_expires_at=None)
    )
    await db.execute(stmt)
    await db.flush()
    logger.info("slot_released", slot_id=str(slot_id))
