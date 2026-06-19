"""
EvalRun and EvalCase ORM models.

EvalRun represents a single execution of the evaluation harness.
EvalCase stores per-case input, expected outcome, actual outcome, and score.
Cases can also live in JSON files (eval/datasets/) for version control —
these models are used when cases are persisted to DB for historical tracking.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EvalRun(Base, UUIDMixin, TimestampMixin):
    """Records metadata and aggregate metrics for one eval harness execution."""

    __tablename__ = "eval_runs"

    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the dataset file used (e.g. booking_cases.json).",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Aggregate metrics: task_success_rate, hallucination_count, etc.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    cases: Mapped[list[EvalCase]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<EvalRun id={self.id!s:.8} name={self.run_name!r}>"


class EvalCase(Base, UUIDMixin):
    """
    A single test case result within an EvalRun.

    score values: "pass" | "partial" | "fail"
    - pass    = correct action completed with valid backend result
    - partial = correct intent but incomplete handling
    - fail    = wrong slot, wrong doctor, hallucinated result, or no completion
    """

    __tablename__ = "eval_cases"

    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    case_id: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Human-readable case identifier."
    )
    case_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="booking | rescheduling | cancellation | conflict | recovery",
    )
    input_scenario: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="The test case definition from the dataset."
    )
    expected_outcome: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    actual_outcome: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    score: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="pass | partial | fail"
    )
    turns_taken: Mapped[Optional[int]] = mapped_column(nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    hallucination_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    tags: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    run: Mapped[Optional[EvalRun]] = relationship(back_populates="cases")

    def __repr__(self) -> str:
        return (
            f"<EvalCase id={self.id!s:.8} "
            f"case_id={self.case_id!r} "
            f"score={self.score!r}>"
        )
