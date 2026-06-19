"""
Availability Pydantic schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.constants import SlotStatus


class SlotRead(BaseModel):
    """A single slot as returned by the availability endpoint."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    slot_status: SlotStatus
    hold_expires_at: Optional[datetime] = None


class AvailabilityQuery(BaseModel):
    """Query parameters for the availability endpoint (as a schema for validation)."""

    clinic_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    date: str  # YYYY-MM-DD
    appointment_type: Optional[str] = None


class AvailabilityResponse(BaseModel):
    """Grouped slot availability for a given date / doctor."""

    date: str
    clinic_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    available_slots: list[SlotRead] = []
    total_available: int = 0
    nearest_alternatives: list[SlotRead] = []  # Populated if no slots on requested date
