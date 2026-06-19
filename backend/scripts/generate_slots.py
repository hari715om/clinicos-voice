#!/usr/bin/env python3
"""
Standalone slot generation script.
Run this daily (via cron or Render scheduled job) to extend the slot window.

Usage (from backend/):
    python scripts/generate_slots.py --clinic-id <UUID> --days 30
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import uuid

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.slot_generator import generate_slots_for_clinic
from app.utils.time_utils import now_ist
import app.models  # noqa: F401

configure_logging()
logger = get_logger("generate_slots")


async def main(clinic_id: str, days: int) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cid = uuid.UUID(clinic_id)
    start = now_ist().date()

    print(f"\nGenerating slots for clinic {cid} — {days} days from {start}")

    async with Session() as db:
        summary = await generate_slots_for_clinic(db, clinic_id=cid, start_date=start, days=days)
        total = sum(summary.values())
        for name, count in summary.items():
            print(f"  {name}: {count} new slots")
        print(f"\nTotal slots created: {total}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate doctor slots")
    parser.add_argument("--clinic-id", required=False, default=settings.CLINIC_ID)
    parser.add_argument("--days", type=int, default=settings.SLOT_GENERATION_DAYS)
    args = parser.parse_args()

    if not args.clinic_id:
        print("ERROR: --clinic-id is required or set CLINIC_ID in .env")
        sys.exit(1)

    asyncio.run(main(args.clinic_id, args.days))
