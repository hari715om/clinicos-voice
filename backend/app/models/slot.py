"""
DoctorSlot ORM model.

Represents a single pre-generated bookable time window for a specific doctor.
Slots are created in bulk by the slot_generator service based on WeeklySchedule data.

State machine:
  AVAILABLE  →  HELD      (agent begins booking flow)
  HELD       →  BOOKED    (appointment committed to DB)
  HELD       →  AVAILABLE (hold expired — SLOT_HOLD_SECONDS elapsed)
  AVAILABLE  →  BLOCKED   (admin blocks the slot)
  BOOKED     →  AVAILABLE (appointment cancelled/rescheduled — slot freed)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import SlotStatus
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.appointment import Appointment


class DoctorSlot(Base, UUIDMixin, TimestampMixin):
    """A concrete, pre-generated bookable time slot for a doctor."""

    __tablename__ = "doctor_slots"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    slot_status: Mapped[SlotStatus] = mapped_column(
        SAEnum(SlotStatus, name="slot_status_enum", create_type=True),
        nullable=False,
        default=SlotStatus.AVAILABLE,
        index=True,
    )
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the HELD status expires and slot reverts to AVAILABLE.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    doctor: Mapped[Doctor] = relationship(back_populates="slots")

    # One-to-one back-reference from Appointment (FK lives on appointments table)
    appointment: Mapped[Optional[Appointment]] = relationship(
        "Appointment",
        back_populates="slot",
        foreign_keys="[Appointment.slot_id]",
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DoctorSlot id={self.id!s:.8} "
            f"doctor_id={self.doctor_id!s:.8} "
            f"start={self.start_time.isoformat() if self.start_time else '?'} "
            f"status={self.slot_status}>"
        )
