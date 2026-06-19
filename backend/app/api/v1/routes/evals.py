"""
Eval routes.

POST /api/v1/evals/run
GET  /api/v1/evals/latest
GET  /api/v1/evals/{run_id}
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.eval import EvalRunCreate, EvalRunRead
from app.services import eval_service

router = APIRouter()


@router.post(
    "/evals/run",
    response_model=EvalRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_eval_run(
    payload: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
) -> EvalRunRead:
    """
    Create a new eval run record.
    Actual execution happens in eval/runners/call_runner.py.
    This endpoint registers the run and returns an ID for the runner to update.
    """
    run = await eval_service.create_eval_run(db, payload.run_name, payload.dataset_name)
    return EvalRunRead.model_validate(run)


@router.get("/evals/latest", response_model=EvalRunRead)
async def get_latest_eval(db: AsyncSession = Depends(get_db)) -> EvalRunRead:
    """Return the most recent eval run."""
    run = await eval_service.get_latest_eval_run(db)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No eval runs found.")
    return EvalRunRead.model_validate(run)


@router.get("/evals/{run_id}", response_model=EvalRunRead)
async def get_eval_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EvalRunRead:
    """Return a specific eval run by ID."""
    run = await eval_service.get_eval_run(db, run_id)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Eval run {run_id} not found.")
    return EvalRunRead.model_validate(run)
