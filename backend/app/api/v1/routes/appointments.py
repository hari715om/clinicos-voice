"""
Appointment routes â€” full CRUD lifecycle.

POST   /api/v1/appointments                          â€” book
PATCH  /api/v1/appointments/{id}                     â€” reschedule
DELETE /api/v1/appointments/{id}                     â€” cancel
GET    /api/v1/appointments/{id}                     â€” get single
GET    /api/v1/patients/{phone}/appointments         â€” list by phone
GET    /api/v1/clinics/{clinic_id}/appointments      â€” list all for clinic (dashboard)
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    AppointmentSummary,
)
from app.services import appointment_service
from app.utils.time_utils import to_ist
from app.core.constants import AppointmentStatus, BookingSource

router = APIRouter()


@router.post(
    "/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def book_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
) -> AppointmentRead:
    """
    Book a new appointment.
    The voice agent calls this after collecting all required details and
    verifying slot availability.
    """
    appointment = await appointment_service.book_appointment(
        db,
        clinic_id=payload.clinic_id,
        patient_name=payload.patient_name,
        phone_number=payload.phone_number,
        doctor_id=payload.doctor_id,
        slot_id=payload.slot_id,
        appointment_type=payload.appointment_type,
        reason=payload.reason,
        booking_source=payload.booking_source,
    )
    await db.refresh(appointment)  # re-load expired attrs before serialisation
    return AppointmentRead.model_validate(appointment)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
) -> AppointmentRead:
    """
    Reschedule an existing appointment to a new slot.
    The old slot is freed; a new appointment record is created linked to the old.
    """
    new_appointment = await appointment_service.reschedule_appointment(
        db,
        appointment_id=appointment_id,
        new_slot_id=payload.new_slot_id,
        reason=payload.reason,
    )
    await db.refresh(new_appointment)  # re-load expired attrs before serialisation
    return AppointmentRead.model_validate(new_appointment)


@router.delete("/appointments/{appointment_id}", response_model=AppointmentRead)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentCancel = AppointmentCancel(),
    db: AsyncSession = Depends(get_db),
) -> AppointmentRead:
    """
    Cancel an appointment. The associated slot is immediately freed.
    """
    appointment = await appointment_service.cancel_appointment(
        db,
        appointment_id=appointment_id,
        reason=payload.reason,
    )
    await db.refresh(appointment)  # re-load expired attrs before serialisation
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AppointmentRead:
    """Return a single appointment by ID."""
    appointment = await appointment_service.get_appointment(db, appointment_id)
    await db.refresh(appointment)
    return AppointmentRead.model_validate(appointment)


@router.get("/patients/{phone_number}/appointments", response_model=list[AppointmentRead])
async def get_patient_appointments(
    phone_number: str,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentRead]:
    """
    Look up all appointments for a patient by phone number.
    Used by the voice agent to find existing bookings for reschedule/cancel.
    """
    appointments = await appointment_service.get_patient_appointments(
        db, phone_number=phone_number, active_only=active_only
    )
    # Refresh each to ensure all columns are loaded before Pydantic serialises
    for a in appointments:
        await db.refresh(a)
    return [AppointmentRead.model_validate(a) for a in appointments]


# â”€â”€ Dashboard â€” clinic-level appointments list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AppointmentDashboardRow(AppointmentRead):
    """Enriched appointment row with patient + doctor + slot data for the admin dashboard."""
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_name: Optional[str] = None
    department_name: Optional[str] = None
    slot_start_time: Optional[str] = None
    slot_end_time: Optional[str] = None


@router.get(
    "/clinics/{clinic_id}/appointments",
    response_model=list[AppointmentDashboardRow],
)
async def list_clinic_appointments(
    clinic_id: uuid.UUID,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentDashboardRow]:
    """
    List all appointments for a clinic with full enriched data (patient, doctor, slot times).
    Used exclusively by the admin dashboard. Supports status filtering and pagination.
    """
    where_clause = "WHERE a.clinic_id = :clinic_id"
    params: dict = {"clinic_id": str(clinic_id), "limit": limit, "offset": offset}
    if status_filter:
        where_clause += " AND a.status::text = :status"
        params["status"] = status_filter.upper()

    sql = text(f"""
        SELECT
            a.id,
            a.clinic_id,
            a.doctor_id,
            a.patient_id,
            a.slot_id,
            a.appointment_type,
            a.status::text                        AS status,
            a.booking_source::text                AS booking_source,
            a.reason,
            a.notes,
            a.cancelled_at,
            a.rescheduled_from_appointment_id,
            a.created_at,
            a.updated_at,
            p.full_name                           AS patient_name,
            p.phone_number                        AS patient_phone,
            d.name                                AS doctor_name,
            dept.name                             AS department_name,
            s.start_time                          AS slot_start_time,
            s.end_time                            AS slot_end_time
        FROM appointments a
        LEFT JOIN patients    p    ON p.id    = a.patient_id
        LEFT JOIN doctors     d    ON d.id    = a.doctor_id
        LEFT JOIN departments dept ON dept.id = d.department_id
        LEFT JOIN doctor_slots s   ON s.id    = a.slot_id
        {where_clause}
        ORDER BY a.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(sql, params)
    rows = result.mappings().all()

    out = []
    for row in rows:
        r = dict(row)
        r["status"] = AppointmentStatus[r["status"]]
        r["booking_source"] = BookingSource[r["booking_source"]]
        for f in ("slot_start_time", "slot_end_time"):
            if r.get(f) is not None:
                r[f] = r[f].isoformat() if hasattr(r[f], "isoformat") else str(r[f])
        out.append(AppointmentDashboardRow(**r))
    return out
