"""
Availability routes.

GET /api/v1/availability
Query params: clinic_id, date (YYYY-MM-DD), doctor_id?, department_id?, appointment_type?
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.availability import AvailabilityResponse, SlotRead
from app.services import availability_service

router = APIRouter()


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(
    clinic_id: uuid.UUID = Query(..., description="Clinic UUID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    doctor_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    appointment_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    """
    Return available slots for a clinic on a given date.
    Expired holds are released before the query runs.
    If no slots are available on the requested date, nearest_alternatives is populated.
    """
    slots = await availability_service.get_available_slots(
        db,
        clinic_id=clinic_id,
        target_date=date,
        doctor_id=doctor_id,
        department_id=department_id,
    )

    slot_reads = [SlotRead.model_validate(s) for s in slots]

    # If no availability, find nearest alternatives
    nearest: list[SlotRead] = []
    if not slots and doctor_id:
        alt_slots = await availability_service.find_nearest_alternatives(
            db, clinic_id=clinic_id, doctor_id=doctor_id, from_date=date
        )
        nearest = [SlotRead.model_validate(s) for s in alt_slots]

    return AvailabilityResponse(
        date=date,
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        available_slots=slot_reads,
        total_available=len(slot_reads),
        nearest_alternatives=nearest,
    )
