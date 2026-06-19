"""
Eval Service — persists and retrieves eval run results.
The eval harness runner (eval/runners/) calls these functions after scoring.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.eval_run import EvalCase, EvalRun
from app.utils.time_utils import now_utc

logger = get_logger(__name__)


async def create_eval_run(
    db: AsyncSession,
    run_name: str,
    dataset_name: str,
) -> EvalRun:
    run = EvalRun(
        run_name=run_name,
        dataset_name=dataset_name,
        started_at=now_utc(),
    )
    db.add(run)
    await db.flush()
    logger.info("eval_run_created", run_id=str(run.id), name=run_name)
    return run


async def finish_eval_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    summary_metrics: dict[str, Any],
) -> EvalRun:
    result = await db.execute(select(EvalRun).where(EvalRun.id == run_id))
    run = result.scalar_one_or_none()
    if run:
        run.ended_at = now_utc()
        run.summary_metrics = summary_metrics
        await db.flush()
    return run


async def get_latest_eval_run(db: AsyncSession) -> Optional[EvalRun]:
    result = await db.execute(
        select(EvalRun).order_by(desc(EvalRun.created_at)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_eval_run(db: AsyncSession, run_id: uuid.UUID) -> Optional[EvalRun]:
    result = await db.execute(select(EvalRun).where(EvalRun.id == run_id))
    return result.scalar_one_or_none()
