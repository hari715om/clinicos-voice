"""
Admin routes — protected by X-Admin-API-Key header.

POST /api/v1/admin/seed-clinic   — trigger seed data load
POST /api/v1/admin/load-slots    — regenerate slots for next N days
GET  /api/v1/admin/stats         — quick stats summary
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import require_admin_key
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.slot import DoctorSlot
from app.services.slot_generator import generate_slots_for_clinic

router = APIRouter()


@router.post(
    "/admin/load-slots",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_key)],
)
async def load_slots(
    clinic_id: uuid.UUID = Query(...),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate DoctorSlot rows for the next `days` days for all active doctors.
    Safe to re-run — idempotent.
    """
    from app.utils.time_utils import now_ist
    summary = await generate_slots_for_clinic(
        db, clinic_id=clinic_id, start_date=now_ist().date(), days=days
    )
    return {
        "status": "ok",
        "slots_created_by_doctor": summary,
        "total_created": sum(summary.values()),
    }


@router.get(
    "/admin/stats",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_key)],
)
async def get_stats(
    clinic_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Quick stats: doctor count, slot count, appointment count, patient count."""
    doctor_count = await db.scalar(select(func.count()).select_from(Doctor))
    patient_count = await db.scalar(select(func.count()).select_from(Patient))
    slot_count = await db.scalar(select(func.count()).select_from(DoctorSlot))
    appt_count = await db.scalar(select(func.count()).select_from(Appointment))

    return {
        "doctors": doctor_count,
        "patients": patient_count,
        "slots_total": slot_count,
        "appointments_total": appt_count,
    }
