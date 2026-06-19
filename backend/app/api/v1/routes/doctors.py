"""
Doctor routes.

GET /api/v1/clinics/{clinic_id}/doctors   — list active doctors
GET /api/v1/doctors/{doctor_id}           — doctor detail
GET /api/v1/doctors/{doctor_id}/schedule  — doctor's weekly schedule
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.doctor import DoctorListItem, DoctorRead
from app.services import clinic_service

router = APIRouter()


@router.get("/clinics/{clinic_id}/doctors", response_model=list[DoctorListItem])
async def list_doctors(
    clinic_id: uuid.UUID,
    department_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[DoctorListItem]:
    """List all active doctors in a clinic, optionally filtered by department."""
    doctors = await clinic_service.list_doctors(db, clinic_id, department_id=department_id)
    return [DoctorListItem.model_validate(d) for d in doctors]


@router.get("/doctors/{doctor_id}", response_model=DoctorRead)
async def get_doctor(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DoctorRead:
    """Return full doctor detail including weekly schedule."""
    doctor = await clinic_service.get_doctor(db, doctor_id)
    return DoctorRead.model_validate(doctor)


@router.get("/doctors/{doctor_id}/schedule", response_model=DoctorRead)
async def get_doctor_schedule(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DoctorRead:
    """Return doctor schedule windows (alias of detail endpoint)."""
    doctor = await clinic_service.get_doctor(db, doctor_id)
    return DoctorRead.model_validate(doctor)
