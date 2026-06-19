"""
Tests for the appointment service — booking, rescheduling, cancellation.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AppointmentStatus, SlotStatus
from app.core.exceptions import (
    AppointmentAlreadyCancelledError,
    SlotNotAvailableError,
)
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.slot import DoctorSlot
from app.services import appointment_service


@pytest.mark.asyncio
async def test_book_appointment_success(
    db: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    patient: Patient,
    available_slot: DoctorSlot,
) -> None:
    """Happy path: book a valid available slot."""
    appt = await appointment_service.book_appointment(
        db,
        clinic_id=clinic.id,
        patient_name=patient.full_name,
        phone_number=patient.phone_number,
        doctor_id=doctor.id,
        slot_id=available_slot.id,
        appointment_type="new_consultation",
        reason="First visit",
    )
    await db.flush()

    assert appt.status == AppointmentStatus.BOOKED
    assert appt.slot_id == available_slot.id

    # Slot must now be BOOKED
    await db.refresh(available_slot)
    assert available_slot.slot_status == SlotStatus.BOOKED


@pytest.mark.asyncio
async def test_book_appointment_already_booked_slot(
    db: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    patient: Patient,
    available_slot: DoctorSlot,
) -> None:
    """Cannot double-book a slot — second attempt must raise SlotNotAvailableError."""
    # First booking
    await appointment_service.book_appointment(
        db,
        clinic_id=clinic.id,
        patient_name=patient.full_name,
        phone_number=patient.phone_number,
        doctor_id=doctor.id,
        slot_id=available_slot.id,
        appointment_type="new_consultation",
    )
    await db.flush()

    # Second booking on same slot must fail
    with pytest.raises(SlotNotAvailableError):
        await appointment_service.book_appointment(
            db,
            clinic_id=clinic.id,
            patient_name="Another Patient",
            phone_number="8888888888",
            doctor_id=doctor.id,
            slot_id=available_slot.id,
            appointment_type="new_consultation",
        )


@pytest.mark.asyncio
async def test_cancel_appointment(
    db: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    patient: Patient,
    available_slot: DoctorSlot,
) -> None:
    """Cancellation frees the slot back to AVAILABLE."""
    appt = await appointment_service.book_appointment(
        db,
        clinic_id=clinic.id,
        patient_name=patient.full_name,
        phone_number=patient.phone_number,
        doctor_id=doctor.id,
        slot_id=available_slot.id,
        appointment_type="new_consultation",
    )
    await db.flush()

    cancelled = await appointment_service.cancel_appointment(db, appointment_id=appt.id)
    await db.flush()

    assert cancelled.status == AppointmentStatus.CANCELLED
    assert cancelled.cancelled_at is not None

    await db.refresh(available_slot)
    assert available_slot.slot_status == SlotStatus.AVAILABLE


@pytest.mark.asyncio
async def test_cancel_already_cancelled_raises(
    db: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    patient: Patient,
    available_slot: DoctorSlot,
) -> None:
    """Double-cancellation raises AppointmentAlreadyCancelledError."""
    appt = await appointment_service.book_appointment(
        db,
        clinic_id=clinic.id,
        patient_name=patient.full_name,
        phone_number=patient.phone_number,
        doctor_id=doctor.id,
        slot_id=available_slot.id,
        appointment_type="new_consultation",
    )
    await db.flush()

    await appointment_service.cancel_appointment(db, appointment_id=appt.id)
    await db.flush()

    with pytest.raises(AppointmentAlreadyCancelledError):
        await appointment_service.cancel_appointment(db, appointment_id=appt.id)


@pytest.mark.asyncio
async def test_get_patient_appointments_by_phone(
    db: AsyncSession,
    clinic: Clinic,
    doctor: Doctor,
    patient: Patient,
    available_slot: DoctorSlot,
) -> None:
    """Patient appointments lookable by phone number."""
    await appointment_service.book_appointment(
        db,
        clinic_id=clinic.id,
        patient_name=patient.full_name,
        phone_number=patient.phone_number,
        doctor_id=doctor.id,
        slot_id=available_slot.id,
        appointment_type="new_consultation",
    )
    await db.flush()

    appointments = await appointment_service.get_patient_appointments(
        db, phone_number=patient.phone_number
    )
    assert len(appointments) == 1
    assert appointments[0].status == AppointmentStatus.BOOKED
