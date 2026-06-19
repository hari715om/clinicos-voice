"""
Clinic routes — GET /api/v1/clinics/{clinic_id}
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.clinic import ClinicRead
from app.services import clinic_service

router = APIRouter()


@router.get("/clinics/{clinic_id}", response_model=ClinicRead)
async def get_clinic(
    clinic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ClinicRead:
    """Return clinic metadata including departments."""
    clinic = await clinic_service.get_clinic(db, clinic_id)
    return ClinicRead.model_validate(clinic)
