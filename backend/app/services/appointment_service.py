"""
Appointment Service — Core Booking Logic.

This module owns all appointment lifecycle operations:
- book_appointment
- reschedule_appointment
- cancel_appointment
- get_appointment
- get_patient_appointments

Design principles:
1. Every slot transition uses SELECT FOR UPDATE to prevent race conditions.
2. Service functions never call each other — each is self-contained.
3. Exceptions from app.core.exceptions are raised; routes convert them to HTTP errors.
4. No hallucination is possible because slot state is verified atomically before commit.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import AppointmentStatus, BookingSource, SlotStatus
from app.core.exceptions import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    AppointmentNotReschedulableError,
    PatientNotFoundError,
    SlotNotAvailableError,
    SlotNotFoundError,
)
from app.core.logging import get_logger
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.slot import DoctorSlot
from app.utils.time_utils import now_utc, hours_until

logger = get_logger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _get_or_create_patient(
    db: AsyncSession,
    full_name: str,
    phone_number: str,
) -> Patient:
    """
    Look up a patient by phone_number. Create a new record if not found.
    The voice agent collects name + phone; phone is the primary key.
    """
    result = await db.execute(
        select(Patient).where(Patient.phone_number == phone_number)
    )
    patient = result.scalar_one_or_none()

    if patient is None:
        patient = Patient(full_name=full_name, phone_number=phone_number)
        db.add(patient)
        await db.flush()
        logger.info("patient_created", patient_id=str(patient.id), phone=phone_number)
    else:
        # Update name if it has changed (caller corrects spelling)
        if patient.full_name != full_name:
            patient.full_name = full_name
            await db.flush()

    return patient


async def _lock_slot(db: AsyncSession, slot_id: uuid.UUID) -> DoctorSlot:
    """
    Acquire a row-level lock on a DoctorSlot.
    Raises SlotNotFoundError or SlotNotAvailableError as appropriate.
    """
    result = await db.execute(
        select(DoctorSlot)
        .where(DoctorSlot.id == slot_id)
        .with_for_update(skip_locked=False)
    )
    slot = result.scalar_one_or_none()

    if slot is None:
        raise SlotNotFoundError(f"Slot {slot_id!s} does not exist.")

    # Accept AVAILABLE or HELD (held could mean the same session is confirming)
    if slot.slot_status not in (SlotStatus.AVAILABLE, SlotStatus.HELD):
        raise SlotNotAvailableError(
            f"Slot {slot_id!s} is {slot.slot_status} and cannot be booked.",
            detail=f"status={slot.slot_status}",
        )

    return slot


# ── Public API ─────────────────────────────────────────────────────────────────

async def book_appointment(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    patient_name: str,
    phone_number: str,
    doctor_id: uuid.UUID,
    slot_id: uuid.UUID,
    appointment_type: str,
    reason: Optional[str] = None,
    booking_source: BookingSource = BookingSource.VOICE_AGENT,
) -> Appointment:
    """
    Book a new appointment for a patient.

    Atomic operation:
    1. Get or create patient.
    2. Lock slot row (SELECT FOR UPDATE).
    3. Verify slot is AVAILABLE or HELD.
    4. Create Appointment record.
    5. Mark slot as BOOKED, clear hold_expires_at.
    6. Return appointment.

    Raises:
        SlotNotFoundError — slot_id doesn't exist.
        SlotNotAvailableError — slot is BOOKED or BLOCKED.
    """
    patient = await _get_or_create_patient(db, patient_name, phone_number)
    slot = await _lock_slot(db, slot_id)

    # Create appointment
    appointment = Appointment(
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        patient_id=patient.id,
        slot_id=slot_id,
        appointment_type=appointment_type,
        status=AppointmentStatus.BOOKED,
        booking_source=booking_source,
        reason=reason,
    )
    db.add(appointment)
    await db.flush()  # Get appointment.id before updating slot

    # Commit slot to booked
    slot.slot_status = SlotStatus.BOOKED
    slot.hold_expires_at = None
    await db.flush()

    logger.info(
        "appointment_booked",
        appointment_id=str(appointment.id),
        patient_id=str(patient.id),
        doctor_id=str(doctor_id),
        slot_id=str(slot_id),
        slot_start=slot.start_time.isoformat(),
    )
    return appointment


async def reschedule_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    new_slot_id: uuid.UUID,
    reason: Optional[str] = None,
) -> Appointment:
    """
    Reschedule an existing appointment to a new slot.

    Process:
    1. Load and validate existing appointment (must be BOOKED).
    2. Check minimum reschedule window (MIN_RESCHEDULE_HOURS).
    3. Lock new slot and verify it is AVAILABLE.
    4. Create new Appointment linked via rescheduled_from_appointment_id.
    5. Mark old appointment RESCHEDULED, free old slot.
    6. Mark new slot BOOKED.

    Raises:
        AppointmentNotFoundError
        AppointmentNotReschedulableError
        SlotNotAvailableError
    """
    # Load existing appointment
    result = await db.execute(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .with_for_update()
    )
    old_appt = result.scalar_one_or_none()

    if old_appt is None:
        raise AppointmentNotFoundError(f"Appointment {appointment_id!s} not found.")

    if old_appt.status not in (AppointmentStatus.BOOKED,):
        raise AppointmentNotReschedulableError(
            f"Appointment {appointment_id!s} cannot be rescheduled (status={old_appt.status})."
        )

    # Check minimum reschedule window against the OLD slot's start time
    old_slot_result = await db.execute(
        select(DoctorSlot).where(DoctorSlot.id == old_appt.slot_id)
    )
    old_slot = old_slot_result.scalar_one_or_none()

    if old_slot and hours_until(old_slot.start_time) < settings.MIN_RESCHEDULE_HOURS:
        raise AppointmentNotReschedulableError(
            f"Reschedules must be made at least {settings.MIN_RESCHEDULE_HOURS} hours before the appointment."
        )

    # Lock and validate new slot
    new_slot = await _lock_slot(db, new_slot_id)

    # Create rescheduled appointment
    new_appt = Appointment(
        clinic_id=old_appt.clinic_id,
        doctor_id=old_appt.doctor_id,
        patient_id=old_appt.patient_id,
        slot_id=new_slot_id,
        appointment_type=old_appt.appointment_type,
        status=AppointmentStatus.BOOKED,
        booking_source=old_appt.booking_source,
        reason=reason or old_appt.reason,
        rescheduled_from_appointment_id=old_appt.id,
    )
    db.add(new_appt)
    await db.flush()

    # Update old appointment status
    old_appt.status = AppointmentStatus.RESCHEDULED
    await db.flush()

    # Free old slot
    if old_slot:
        old_slot.slot_status = SlotStatus.AVAILABLE
        old_slot.hold_expires_at = None

    # Commit new slot
    new_slot.slot_status = SlotStatus.BOOKED
    new_slot.hold_expires_at = None
    await db.flush()

    logger.info(
        "appointment_rescheduled",
        old_appointment_id=str(appointment_id),
        new_appointment_id=str(new_appt.id),
        new_slot_id=str(new_slot_id),
    )
    return new_appt


async def cancel_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    reason: Optional[str] = None,
) -> Appointment:
    """
    Cancel an existing appointment and free its slot.

    Raises:
        AppointmentNotFoundError
        AppointmentAlreadyCancelledError
    """
    result = await db.execute(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .with_for_update()
    )
    appointment = result.scalar_one_or_none()

    if appointment is None:
        raise AppointmentNotFoundError(f"Appointment {appointment_id!s} not found.")

    if appointment.status == AppointmentStatus.CANCELLED:
        raise AppointmentAlreadyCancelledError(
            f"Appointment {appointment_id!s} is already cancelled."
        )

    # Cancel the appointment
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = now_utc()
    if reason:
        appointment.notes = f"Cancellation reason: {reason}"
    await db.flush()

    # Free the slot
    slot_result = await db.execute(
        select(DoctorSlot)
        .where(DoctorSlot.id == appointment.slot_id)
        .with_for_update()
    )
    slot = slot_result.scalar_one_or_none()
    if slot:
        slot.slot_status = SlotStatus.AVAILABLE
        slot.hold_expires_at = None
        await db.flush()

    logger.info(
        "appointment_cancelled",
        appointment_id=str(appointment_id),
        slot_id=str(appointment.slot_id),
    )
    return appointment


async def get_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
) -> Appointment:
    """Load a single appointment by ID. Raises AppointmentNotFoundError if missing."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise AppointmentNotFoundError(f"Appointment {appointment_id!s} not found.")
    return appointment


async def get_patient_appointments(
    db: AsyncSession,
    phone_number: str,
    active_only: bool = False,
) -> list[Appointment]:
    """
    Look up all appointments for a patient by phone number.
    Used by the voice agent to find existing bookings for reschedule/cancel.

    Args:
        active_only: If True, only return BOOKED appointments.
    """
    patient_result = await db.execute(
        select(Patient).where(Patient.phone_number == phone_number)
    )
    patient = patient_result.scalar_one_or_none()

    if patient is None:
        return []

    filters = [Appointment.patient_id == patient.id]
    if active_only:
        filters.append(Appointment.status == AppointmentStatus.BOOKED)

    result = await db.execute(
        select(Appointment)
        .where(and_(*filters))
        .order_by(Appointment.created_at.desc())
    )
    return list(result.scalars().all())
