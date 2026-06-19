"""
Clinic and Department Pydantic schemas.
Used for serializing API responses — never for business logic.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None


class ClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    phone_number: Optional[str] = None
    website_url: Optional[str] = None
    timezone: str
    departments: list[DepartmentRead] = []
