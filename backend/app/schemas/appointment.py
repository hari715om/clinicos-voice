"""
Appointment Pydantic schemas — request and response models.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.constants import AppointmentStatus, BookingSource


class AppointmentCreate(BaseModel):
    """Payload for POST /api/v1/appointments — used by both API and agent tools."""

    clinic_id: uuid.UUID
    patient_name: str
    phone_number: str
    doctor_id: uuid.UUID
    slot_id: uuid.UUID
    appointment_type: str  # new_consultation | follow_up | review | emergency
    reason: Optional[str] = None
    booking_source: BookingSource = BookingSource.VOICE_AGENT

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Strip non-digit characters and ensure minimum length."""
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return digits


class AppointmentReschedule(BaseModel):
    """Payload for PATCH /api/v1/appointments/{id} — reschedule to a new slot."""

    new_slot_id: uuid.UUID
    reason: Optional[str] = None


class AppointmentCancel(BaseModel):
    """Payload for DELETE /api/v1/appointments/{id}."""

    reason: Optional[str] = None


class AppointmentRead(BaseModel):
    """Full appointment detail — returned after booking/rescheduling."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    slot_id: uuid.UUID
    appointment_type: str
    status: AppointmentStatus
    booking_source: BookingSource
    reason: Optional[str] = None
    notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    rescheduled_from_appointment_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class AppointmentSummary(BaseModel):
    """Lightweight summary for patient appointment list."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_type: str
    status: AppointmentStatus
    doctor_name: Optional[str] = None
    department_name: Optional[str] = None
    slot_start_time: Optional[datetime] = None
    slot_end_time: Optional[datetime] = None
    created_at: datetime
