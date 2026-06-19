"""
Slot Generator Service.

Generates DoctorSlot rows from WeeklySchedule entries.
Designed to be idempotent — safe to re-run without creating duplicates.

Usage (from scripts/generate_slots.py):
    asyncio.run(generate_slots_for_all_doctors(clinic_id, days=30))
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import SlotStatus
from app.core.logging import get_logger
from app.models.doctor import Doctor, WeeklySchedule
from app.models.slot import DoctorSlot
from app.utils.time_utils import ist_datetime, date_range, now_utc

logger = get_logger(__name__)


async def generate_slots_for_doctor(
    db: AsyncSession,
    doctor: Doctor,
    start_date: date,
    days: int = 30,
) -> int:
    """
    Generate DoctorSlot rows for a doctor over the given date range.

    Returns the count of newly inserted slots.
    Skips any slot that already exists (idempotent).
    """
    if not doctor.weekly_schedules:
        logger.warning("no_schedules_for_doctor", doctor_id=str(doctor.id), name=doctor.name)
        return 0

    created_count = 0
    dates = date_range(start_date, days)

    for d in dates:
        weekday = d.weekday()  # 0=Mon, 6=Sun

        # Find all schedule blocks active on this weekday
        day_schedules = [
            s for s in doctor.weekly_schedules
            if s.day_of_week == weekday and s.is_active
        ]

        for schedule in day_schedules:
            # Generate slots within this block
            slot_start = ist_datetime(d, schedule.start_time)
            block_end = ist_datetime(d, schedule.end_time)
            duration = timedelta(minutes=schedule.slot_duration_minutes)

            while slot_start + duration <= block_end:
                slot_end = slot_start + duration

                # Skip slots in the past
                if slot_end <= now_utc():
                    slot_start = slot_end
                    continue

                # Idempotency: check if slot already exists
                existing = await db.execute(
                    select(DoctorSlot).where(
                        and_(
                            DoctorSlot.doctor_id == doctor.id,
                            DoctorSlot.start_time == slot_start,
                        )
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    slot_start = slot_end
                    continue

                # Create the slot
                slot = DoctorSlot(
                    doctor_id=doctor.id,
                    clinic_id=doctor.clinic_id,
                    start_time=slot_start,
                    end_time=slot_end,
                    slot_status=SlotStatus.AVAILABLE,
                )
                db.add(slot)
                created_count += 1
                slot_start = slot_end

    await db.flush()
    logger.info(
        "slots_generated",
        doctor_id=str(doctor.id),
        doctor_name=doctor.name,
        days=days,
        created=created_count,
    )
    return created_count


async def generate_slots_for_clinic(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    start_date: Optional[date] = None,
    days: int = 30,
) -> dict[str, int]:
    """
    Generate slots for all active doctors in a clinic.

    Returns a dict mapping doctor name → slots created.
    """
    if start_date is None:
        from app.utils.time_utils import now_ist
        start_date = now_ist().date()

    result_map = await db.execute(
        select(Doctor).where(
            and_(Doctor.clinic_id == clinic_id, Doctor.active == True)  # noqa: E712
        )
    )
    doctors = result_map.scalars().all()

    summary: dict[str, int] = {}
    for doctor in doctors:
        # Load schedules
        schedule_result = await db.execute(
            select(WeeklySchedule).where(
                and_(
                    WeeklySchedule.doctor_id == doctor.id,
                    WeeklySchedule.is_active == True,  # noqa: E712
                )
            )
        )
        doctor.weekly_schedules = list(schedule_result.scalars().all())
        count = await generate_slots_for_doctor(db, doctor, start_date, days)
        summary[doctor.name] = count

    await db.commit()
    return summary
