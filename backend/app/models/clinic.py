"""
Clinic and Department ORM models.

Clinic is the top-level entity — all other entities FK to clinic.id.
For ClinicOS Voice, a single Clinic row represents Utkal Hospital.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.doctor import Doctor


class Clinic(Base, UUIDMixin, TimestampMixin):
    """Represents Utkal Hospital — the single clinic in scope."""

    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Kolkata"
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    departments: Mapped[list[Department]] = relationship(
        back_populates="clinic",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    doctors: Mapped[list[Doctor]] = relationship(
        back_populates="clinic",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Clinic id={self.id!s:.8} name={self.name!r}>"


class Department(Base, UUIDMixin, TimestampMixin):
    """A clinical department — e.g. Neurology, Dentistry."""

    __tablename__ = "departments"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    clinic: Mapped[Clinic] = relationship(back_populates="departments")
    doctors: Mapped[list[Doctor]] = relationship(
        back_populates="department",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id!s:.8} name={self.name!r}>"
