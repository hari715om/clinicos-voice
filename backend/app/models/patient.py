"""
Patient ORM model.

Patients are identified by phone_number in voice interactions.
The voice agent uses phone_number as the primary lookup key when
a patient calls in — full_name is collected or confirmed during the call.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment


class Patient(Base, UUIDMixin, TimestampMixin):
    """A registered patient at Utkal Hospital."""

    __tablename__ = "patients"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Primary lookup key used by the voice agent.",
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal clinical notes — not exposed to the voice agent.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="patient",
        lazy="selectin",
        order_by="Appointment.created_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Patient id={self.id!s:.8} "
            f"name={self.full_name!r} "
            f"phone={self.phone_number!r}>"
        )
