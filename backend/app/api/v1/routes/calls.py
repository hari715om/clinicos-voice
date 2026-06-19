"""
Call session routes — session lifecycle and event logging.

POST /api/v1/calls/start
POST /api/v1/calls/{session_id}/event
POST /api/v1/calls/{session_id}/end
GET  /api/v1/calls/{session_id}
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.call import (
    CallEventCreate,
    CallEventRead,
    CallSessionCreate,
    CallSessionEnd,
    CallSessionRead,
)
from app.services import call_service

router = APIRouter()


@router.post(
    "/calls/start",
    response_model=CallSessionRead,
    status_code=status.HTTP_201_CREATED,
)
async def start_call(
    payload: CallSessionCreate,
    db: AsyncSession = Depends(get_db),
) -> CallSessionRead:
    """Create a new call session. Called by the LiveKit agent at session start."""
    session = await call_service.create_session(
        db,
        clinic_id=payload.clinic_id,
        patient_phone=payload.patient_phone,
        livekit_room_name=payload.livekit_room_name,
        agent_provider=payload.agent_provider,
    )
    return CallSessionRead.model_validate(session)


@router.post(
    "/calls/{session_id}/event",
    response_model=CallEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def log_event(
    session_id: uuid.UUID,
    payload: CallEventCreate,
    db: AsyncSession = Depends(get_db),
) -> CallEventRead:
    """Append an event to a call session's log."""
    event = await call_service.log_event(
        db,
        session_id=session_id,
        event_type=payload.event_type,
        event_payload=payload.event_payload,
    )
    return CallEventRead.model_validate(event)


@router.post("/calls/{session_id}/end", response_model=CallSessionRead)
async def end_call(
    session_id: uuid.UUID,
    payload: CallSessionEnd = CallSessionEnd(),
    db: AsyncSession = Depends(get_db),
) -> CallSessionRead:
    """Mark a call session as ended."""
    session = await call_service.end_session(db, session_id=session_id, summary=payload.summary)
    return CallSessionRead.model_validate(session)


@router.get("/calls/{session_id}", response_model=CallSessionRead)
async def get_call(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CallSessionRead:
    """Return a call session by ID."""
    session = await call_service.get_session(db, session_id)
    if session is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call session not found.")
    return CallSessionRead.model_validate(session)
