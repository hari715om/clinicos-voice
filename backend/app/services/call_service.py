"""
Call Session Service — tracks voice call lifecycle and events.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CallStatus
from app.core.logging import get_logger
from app.models.call_session import CallEvent, CallSession
from app.utils.time_utils import now_utc

logger = get_logger(__name__)


async def create_session(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    patient_phone: Optional[str] = None,
    livekit_room_name: Optional[str] = None,
    agent_provider: str = "livekit",
) -> CallSession:
    """Create and persist a new CallSession at the start of a voice call."""
    session = CallSession(
        clinic_id=clinic_id,
        patient_phone=patient_phone,
        livekit_room_name=livekit_room_name,
        agent_provider=agent_provider,
        status=CallStatus.ACTIVE,
        started_at=now_utc(),
    )
    db.add(session)
    await db.flush()
    logger.info("call_session_created", session_id=str(session.id))
    return session


async def log_event(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_type: str,
    event_payload: dict[str, Any],
) -> CallEvent:
    """Append an event to a call session's event log."""
    event = CallEvent(
        call_session_id=session_id,
        event_type=event_type,
        event_payload=event_payload,
        created_at=now_utc(),
    )
    db.add(event)
    await db.flush()
    return event


async def end_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    summary: Optional[str] = None,
    status: CallStatus = CallStatus.ENDED,
) -> CallSession:
    """Mark a call session as ended."""
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    session = result.scalar_one_or_none()
    if session:
        session.status = status
        session.ended_at = now_utc()
        session.summary = summary
        await db.flush()
        logger.info("call_session_ended", session_id=str(session_id), status=status)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> Optional[CallSession]:
    result = await db.execute(select(CallSession).where(CallSession.id == session_id))
    return result.scalar_one_or_none()
