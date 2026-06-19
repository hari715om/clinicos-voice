"""
Doctor and WeeklySchedule ORM models.

WeeklySchedule encodes the recurring availability pattern per doctor.
The slot_generator service uses these rows to pre-generate concrete DoctorSlot entries.
"""
from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic, Department
    from app.models.slot import DoctorSlot
    from app.models.appointment import Appointment


class Doctor(Base, UUIDMixin, TimestampMixin):
    """A clinician practicing at Utkal Hospital."""

    __tablename__ = "doctors"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specialization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consultation_fee: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    clinic: Mapped[Clinic] = relationship(back_populates="doctors")
    department: Mapped[Optional[Department]] = relationship(back_populates="doctors")
    weekly_schedules: Mapped[list[WeeklySchedule]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slots: Mapped[list[DoctorSlot]] = relationship(
        back_populates="doctor",
        lazy="dynamic",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="doctor",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Doctor id={self.id!s:.8} name={self.name!r} active={self.active}>"


class WeeklySchedule(Base, UUIDMixin, TimestampMixin):
    """
    A recurring weekly availability block for a doctor.

    Fields:
    - day_of_week: 0=Monday … 6=Sunday (matches datetime.weekday())
    - start_time / end_time: time-of-day boundaries for the block
    - slot_duration_minutes: granularity of individual slots within this block

    One doctor can have multiple blocks per day (e.g. morning 09:00–13:00
    and afternoon 14:00–17:00) — each gets its own WeeklySchedule row.
    """

    __tablename__ = "weekly_schedules"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0=Monday, 6=Sunday"
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    doctor: Mapped[Doctor] = relationship(back_populates="weekly_schedules")

    def __repr__(self) -> str:
        _days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_name = _days[self.day_of_week] if 0 <= self.day_of_week <= 6 else "?"
        return (
            f"<WeeklySchedule doctor_id={self.doctor_id!s:.8} "
            f"day={day_name} {self.start_time}–{self.end_time} "
            f"duration={self.slot_duration_minutes}min>"
        )
