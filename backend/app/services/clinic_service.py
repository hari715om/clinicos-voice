"""
Clinic and Doctor query services.
Read-only queries — no state mutation.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicNotFoundError, DepartmentNotFoundError, DoctorNotFoundError
from app.models.clinic import Clinic, Department
from app.models.doctor import Doctor


async def get_clinic(db: AsyncSession, clinic_id: uuid.UUID) -> Clinic:
    result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = result.scalar_one_or_none()
    if clinic is None:
        raise ClinicNotFoundError(f"Clinic {clinic_id!s} not found.")
    return clinic


async def list_departments(db: AsyncSession, clinic_id: uuid.UUID) -> list[Department]:
    result = await db.execute(
        select(Department).where(Department.clinic_id == clinic_id).order_by(Department.name)
    )
    return list(result.scalars().all())


async def get_department(db: AsyncSession, department_id: uuid.UUID) -> Department:
    result = await db.execute(select(Department).where(Department.id == department_id))
    dept = result.scalar_one_or_none()
    if dept is None:
        raise DepartmentNotFoundError(f"Department {department_id!s} not found.")
    return dept


async def list_doctors(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    department_id: Optional[uuid.UUID] = None,
    active_only: bool = True,
) -> list[Doctor]:
    filters = [Doctor.clinic_id == clinic_id]
    if active_only:
        filters.append(Doctor.active == True)  # noqa: E712
    if department_id:
        filters.append(Doctor.department_id == department_id)

    result = await db.execute(
        select(Doctor).where(and_(*filters)).order_by(Doctor.name)
    )
    return list(result.scalars().all())


async def get_doctor(db: AsyncSession, doctor_id: uuid.UUID) -> Doctor:
    result = await db.execute(select(Doctor).where(Doctor.id == doctor_id))
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise DoctorNotFoundError(f"Doctor {doctor_id!s} not found.")
    return doctor
