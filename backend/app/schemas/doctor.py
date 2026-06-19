"""
Doctor and WeeklySchedule Pydantic schemas.
"""
from __future__ import annotations

import uuid
from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WeeklyScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool


class DoctorListItem(BaseModel):
    """Lightweight doctor info for list responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    qualification: Optional[str] = None
    specialization: Optional[str] = None
    consultation_fee: Optional[float] = None
    department_id: Optional[uuid.UUID] = None
    active: bool


class DoctorRead(DoctorListItem):
    """Full doctor info including schedule — for detail endpoints."""
    weekly_schedules: list[WeeklyScheduleRead] = []
