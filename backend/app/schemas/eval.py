"""
Eval harness Pydantic schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class EvalRunCreate(BaseModel):
    """Payload for POST /api/v1/evals/run."""

    run_name: str
    dataset_name: str  # e.g. "booking_cases"


class EvalRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_name: str
    dataset_name: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    summary_metrics: Optional[dict[str, Any]] = None
    created_at: datetime


class EvalCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: str
    case_type: str
    score: Optional[str] = None
    turns_taken: Optional[int] = None
    latency_ms: Optional[float] = None
    hallucination_detected: bool
    expected_outcome: dict[str, Any]
    actual_outcome: Optional[dict[str, Any]] = None
    tags: Optional[dict[str, Any]] = None
