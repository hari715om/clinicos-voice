#!/usr/bin/env python3
"""
Cleanup script — reset test appointments and free their slots.

Usage (from backend/):
    # Preview only — show counts without deleting
    python scripts/reset_appointments.py --dry-run

    # Remove ALL appointments (clean slate for live testing)
    python scripts/reset_appointments.py

    # Only remove eval/admin-sourced bookings, keep voice-agent ones
    python scripts/reset_appointments.py --eval-only
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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


async def main(dry_run: bool, eval_only: bool) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # ── Count current state ────────────────────────────────────────────────
        total_appts = (await db.execute(text("SELECT COUNT(*) FROM appointments"))).scalar()
        booked_slots = (await db.execute(
            text("SELECT COUNT(*) FROM doctor_slots WHERE slot_status::text != 'AVAILABLE'")
        )).scalar()

        print(f"\n{'='*52}")
        print(f"  Current database state:")
        print(f"    Total appointments  : {total_appts}")
        print(f"    Non-available slots : {booked_slots}")
        print(f"{'='*52}")

        if dry_run:
            print("\n  [DRY RUN] No changes made.")
            print("  Re-run without --dry-run to apply.\n")
            await engine.dispose()
            return

        # Build the appointment filter clause
        if eval_only:
            appt_where = "WHERE booking_source::text = 'ADMIN'"
            mode_label  = "eval/admin-sourced appointments only"
        else:
            appt_where  = ""
            mode_label  = "ALL appointments"

        print(f"\n  Deleting {mode_label}...")

        # Step 1: Collect the slot IDs that will be freed
        slot_rows = await db.execute(
            text(f"SELECT slot_id FROM appointments {appt_where}")
        )
        slot_ids = [str(r[0]) for r in slot_rows.fetchall()]

        if not slot_ids:
            print("  Nothing matched the filter — database already clean.\n")
            await engine.dispose()
            return

        print(f"  Found {len(slot_ids)} appointment(s) to remove.")

        # Step 2: Break self-referential FK links (reschedule chains) first
        #         so the DELETE doesn't violate the ON DELETE SET NULL FK.
        if eval_only:
            await db.execute(text("""
                UPDATE appointments
                SET rescheduled_from_appointment_id = NULL
                WHERE id IN (SELECT id FROM appointments WHERE booking_source::text = 'ADMIN')
            """))
        else:
            await db.execute(text(
                "UPDATE appointments SET rescheduled_from_appointment_id = NULL"
            ))

        # Step 3: Delete the appointments
        deleted = await db.execute(text(f"DELETE FROM appointments {appt_where}"))
        print(f"  ✔ Deleted {deleted.rowcount} appointment record(s).")

        # Step 4: Free the slots — reset to AVAILABLE using the proper enum cast
        if slot_ids:
            placeholders = ", ".join(f"'{sid}'::uuid" for sid in slot_ids)
            freed = await db.execute(text(f"""
                UPDATE doctor_slots
                SET slot_status    = 'AVAILABLE'::slot_status_enum,
                    hold_expires_at = NULL
                WHERE id IN ({placeholders})
            """))
            print(f"  ✔ Freed {freed.rowcount} slot(s) back to AVAILABLE.")

        # Step 5: Commit
        await db.commit()

        # Verify
        remaining = (await db.execute(text("SELECT COUNT(*) FROM appointments"))).scalar()
        free_slots = (await db.execute(
            text("SELECT COUNT(*) FROM doctor_slots WHERE slot_status::text = 'AVAILABLE'")
        )).scalar()

        print(f"\n  ✅ Done!")
        print(f"     Remaining appointments : {remaining}")
        print(f"     Available slots        : {free_slots}")
        print()

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reset test appointments and free slots for live testing."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts without making any changes.",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Only delete admin/eval bookings. Keeps voice-agent bookings.",
    )
    args = parser.parse_args()

    if not settings.DATABASE_URL:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    asyncio.run(main(dry_run=args.dry_run, eval_only=args.eval_only))
