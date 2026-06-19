"""
Call session and event Pydantic schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.core.constants import CallStatus, CallEventType


class CallSessionCreate(BaseModel):
    """Payload for POST /api/v1/calls/start."""

    clinic_id: uuid.UUID
    patient_phone: Optional[str] = None
    livekit_room_name: Optional[str] = None
    agent_provider: str = "livekit"


class CallSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    patient_phone: Optional[str] = None
    livekit_room_name: Optional[str] = None
    agent_provider: str
    status: CallStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None
    created_at: datetime


class CallEventCreate(BaseModel):
    """Payload for POST /api/v1/calls/{session_id}/event."""

    event_type: CallEventType
    event_payload: dict[str, Any] = {}


class CallEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_session_id: uuid.UUID
    event_type: str
    event_payload: dict[str, Any]
    created_at: datetime


class CallSessionEnd(BaseModel):
    """Payload for POST /api/v1/calls/{session_id}/end."""

    summary: Optional[str] = None
