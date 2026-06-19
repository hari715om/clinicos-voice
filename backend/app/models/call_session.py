"""
CallSession and CallEvent ORM models.

CallSession tracks each patient voice interaction from start to end.
CallEvent provides a granular, append-only event log within a session —
used for analytics, debugging, and eval harness replay.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CallStatus, CallEventType
from app.db.base import Base, TimestampMixin, UUIDMixin


class CallSession(Base, UUIDMixin, TimestampMixin):
    """Represents a single patient voice interaction session."""

    __tablename__ = "call_sessions"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Caller's phone number — may be unknown at session start.",
    )
    livekit_room_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    agent_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="livekit"
    )
    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, name="call_status_enum", create_type=True),
        nullable=False,
        default=CallStatus.ACTIVE,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="LLM-generated or rule-based summary of the call outcome.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    events: Mapped[list[CallEvent]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CallEvent.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<CallSession id={self.id!s:.8} "
            f"phone={self.patient_phone!r} "
            f"status={self.status}>"
        )


class CallEvent(Base, UUIDMixin):
    """
    A single event emitted during a CallSession.
    Append-only — events are never updated or deleted.
    """

    __tablename__ = "call_events"

    call_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    event_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Structured payload — contents vary by event_type.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Event timestamp — always UTC.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    session: Mapped[CallSession] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<CallEvent id={self.id!s:.8} "
            f"type={self.event_type!r} "
            f"session_id={self.call_session_id!s:.8}>"
        )
