"""
Slot maintenance script — diagnose and optionally reset eval-created bookings.
Usage:
    python scripts/check_slots.py           # diagnose only
    python scripts/check_slots.py --reset   # reset eval-booked slots to available
"""
import asyncio
import sys
import pathlib
import argparse

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).parent.parent / ".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main(reset: bool = False) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:

        # 1. Slot status breakdown (uses enum text cast)
        r = await conn.execute(text(
            "SELECT slot_status::text, COUNT(*) AS cnt FROM doctor_slots GROUP BY slot_status::text ORDER BY slot_status::text"
        ))
        print("=== Slot Status Breakdown ===")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # 2. Available slots per day (next 10 days) — enum stored as uppercase
        r2 = await conn.execute(text("""
            SELECT DATE(start_time AT TIME ZONE 'Asia/Kolkata') AS d, COUNT(*)
            FROM doctor_slots
            WHERE slot_status::text = 'AVAILABLE' AND start_time > NOW()
            GROUP BY d ORDER BY d LIMIT 10
        """))
        print("\n=== Available Slots by Date (next 10 days) ===")
        rows = r2.fetchall()
        if rows:
            for row in rows:
                print(f"  {row[0]}: {row[1]} slots")
        else:
            print("  NONE — no available future slots!")

        # 3. Future booked slots
        r3 = await conn.execute(text("""
            SELECT DATE(start_time AT TIME ZONE 'Asia/Kolkata') AS d, COUNT(*)
            FROM doctor_slots
            WHERE slot_status::text = 'BOOKED' AND start_time > NOW()
            GROUP BY d ORDER BY d LIMIT 10
        """))
        print("\n=== Future Booked Slots by Date ===")
        rows3 = r3.fetchall()
        if rows3:
            for row in rows3:
                print(f"  {row[0]}: {row[1]} booked")
        else:
            print("  None booked in future")

        # 4. Total future slots
        r4 = await conn.execute(text(
            "SELECT COUNT(*) FROM doctor_slots WHERE start_time > NOW()"
        ))
        print(f"\n=== Total Future Slots: {r4.scalar()} ===")

        if reset:
            # PostgreSQL SAEnum stores Python Enum NAMES (uppercase), not values.
            # Reset all future slots booked via eval harness (booking_source = 'admin')
            r5 = await conn.execute(text("""
                UPDATE doctor_slots
                SET slot_status = 'AVAILABLE'::slot_status_enum,
                    updated_at  = NOW()
                WHERE slot_status::text = 'BOOKED'
                  AND start_time > NOW()
                  AND id IN (
                      SELECT slot_id FROM appointments
                      WHERE booking_source::text = 'admin'
                        AND status::text         = 'BOOKED'
                  )
            """))
            freed = r5.rowcount

            # Cancel those appointments
            r6 = await conn.execute(text("""
                UPDATE appointments
                SET status       = 'CANCELLED'::appointment_status_enum,
                    cancelled_at = NOW(),
                    updated_at   = NOW()
                WHERE booking_source::text = 'admin'
                  AND status::text         = 'BOOKED'
            """))
            await conn.commit()
            print(f"\n OK: Reset {freed} eval-booked slots back to AVAILABLE")
            print(f"    Cancelled {r6.rowcount} eval appointments")
        else:
            print("\n(Run with --reset to free up eval-booked slots)")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset eval-booked slots to available")
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset))
