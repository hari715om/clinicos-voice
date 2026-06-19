"""
Appointment ORM model.

Central entity linking Patient ↔ Doctor ↔ DoctorSlot.
Supports the full lifecycle: booked → rescheduled / cancelled / completed / no_show.

Key constraints:
- slot_id has a UNIQUE constraint: one appointment per slot at most.
- rescheduled_from_appointment_id creates a linked-list audit trail of reschedules.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AppointmentStatus, BookingSource
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor
    from app.models.patient import Patient
    from app.models.slot import DoctorSlot


class Appointment(Base, UUIDMixin, TimestampMixin):
    """A confirmed appointment linking a patient to a doctor slot."""

    __tablename__ = "appointments"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctor_slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,  # Enforces one active appointment per slot at DB level
    )

    # Appointment metadata
    appointment_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="new_consultation | follow_up | review | emergency",
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointment_status_enum", create_type=True),
        nullable=False,
        default=AppointmentStatus.BOOKED,
        index=True,
    )
    booking_source: Mapped[BookingSource] = mapped_column(
        SAEnum(BookingSource, name="booking_source_enum", create_type=True),
        nullable=False,
        default=BookingSource.VOICE_AGENT,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Lifecycle timestamps
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Self-referential: tracks which appointment this was rescheduled from
    rescheduled_from_appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Pointer to the original appointment that was rescheduled into this one.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    clinic: Mapped[Clinic] = relationship()
    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
    patient: Mapped[Patient] = relationship(back_populates="appointments")

    slot: Mapped[DoctorSlot] = relationship(
        back_populates="appointment",
        foreign_keys=[slot_id],
    )

    # Self-referential — the previous appointment in a reschedule chain
    rescheduled_from: Mapped[Optional[Appointment]] = relationship(
        "Appointment",
        foreign_keys=[rescheduled_from_appointment_id],
        remote_side="Appointment.id",
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id!s:.8} "
            f"patient_id={self.patient_id!s:.8} "
            f"doctor_id={self.doctor_id!s:.8} "
            f"status={self.status}>"
        )
