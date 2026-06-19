#!/usr/bin/env python3
"""
ClinicOS Voice — Master Seed Script for Utkal Hospital.

Populates PostgreSQL with:
  1. Clinic          — Utkal Hospital
  2. Departments     — Neurology, Endocrinology, Dentistry, Physiotherapy
  3. Doctors         — 6 doctors with qualifications
  4. Weekly Schedules — per-doctor availability blocks
  5. Doctor Slots     — concrete slots for next 30 days
  6. Sample Patients  — 10 realistic patient records
  7. Sample Appointments — 15 existing appointments

Usage (from backend/ directory):
    python scripts/seed_clinic.py

Environment:
    Reads DATABASE_URL_SYNC from .env or environment.
    Set SLOT_GENERATION_DAYS to control how many days of slots are generated.

Idempotent: re-running the script will not create duplicates.
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

# Ensure backend/ is in sys.path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env before importing settings
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.constants import AppointmentStatus, BookingSource, SlotStatus
from app.core.logging import configure_logging, get_logger
from app.db.base import Base
from app.models.clinic import Clinic, Department
from app.models.doctor import Doctor, WeeklySchedule
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.slot import DoctorSlot
import app.models  # noqa: F401 — ensure all models are registered

configure_logging()
logger = get_logger("seed")

# ── CSV paths (relative to project root, one level above backend/) ─────────────
PROJECT_ROOT = BACKEND_DIR.parent
CSV_DEPARTMENTS = PROJECT_ROOT / "departments.csv"
CSV_DOCTORS = PROJECT_ROOT / "doctors.csv"
CSV_CONSULTATION_TYPES = PROJECT_ROOT / "consultation_types.csv"
CSV_CLINIC_RULES = PROJECT_ROOT / "clinic_rules.csv"


# ── Seed data definitions ──────────────────────────────────────────────────────

UTKAL_HOSPITAL = {
    "name": "Utkal Hospital",
    "address": "Bhubaneswar, Odisha",
    "city": "Bhubaneswar",
    "phone_number": "+91-674-2300000",
    "website_url": "https://utkalhospital.com",
    "timezone": "Asia/Kolkata",
}

# Weekly schedule blocks per doctor (name → list of schedule dicts)
# Each dict: {days: [0-6], start: "HH:MM", end: "HH:MM", duration: minutes}
DOCTOR_SCHEDULES: dict[str, list[dict[str, Any]]] = {
    "Dr. Amitav Rath": [
        {"days": [0, 2, 4], "start": "09:00", "end": "13:00", "duration": 30},  # Mon,Wed,Fri AM
        {"days": [0, 2, 4], "start": "14:00", "end": "17:00", "duration": 30},  # Mon,Wed,Fri PM
    ],
    "Dr. Akash Gupta": [
        {"days": [1, 3, 5], "start": "09:00", "end": "13:00", "duration": 30},  # Tue,Thu,Sat AM
        {"days": [1, 3, 5], "start": "14:00", "end": "17:00", "duration": 30},  # Tue,Thu,Sat PM
    ],
    "Dr. Madhusmita Sahu": [
        {"days": [0, 1, 2, 3, 4], "start": "10:00", "end": "13:00", "duration": 30},  # Mon-Fri AM
        {"days": [0, 1, 2, 3, 4], "start": "14:00", "end": "16:00", "duration": 30},  # Mon-Fri PM
    ],
    "Dr. Dibyalochan Swain": [
        {"days": [0, 1, 2, 3, 4, 5], "start": "09:00", "end": "13:00", "duration": 30},  # Mon-Sat AM
        {"days": [0, 1, 2, 3, 4, 5], "start": "15:00", "end": "18:00", "duration": 30},  # Mon-Sat PM
    ],
    "Dr. Mithilesh Kumar": [
        {"days": [0, 1, 2, 3, 4], "start": "08:00", "end": "12:00", "duration": 30},  # Mon-Fri AM
        {"days": [0, 1, 2, 3, 4], "start": "14:00", "end": "17:00", "duration": 30},  # Mon-Fri PM
    ],
    "Dr. Mukesh Kumar": [
        {"days": [0, 1, 2, 3, 4, 5], "start": "09:00", "end": "13:00", "duration": 30},  # Mon-Sat AM
        {"days": [0, 1, 2, 3, 4, 5], "start": "14:00", "end": "18:00", "duration": 30},  # Mon-Sat PM
    ],
}

SAMPLE_PATIENTS = [
    {"full_name": "Rajesh Kumar Mohanty", "phone_number": "9861234567", "email": "rajesh.m@email.com"},
    {"full_name": "Priya Dash", "phone_number": "8763456789", "email": "priya.d@email.com"},
    {"full_name": "Suresh Panda", "phone_number": "7894561230", "email": None},
    {"full_name": "Anita Sahoo", "phone_number": "9937812345", "email": "anita.s@email.com"},
    {"full_name": "Bikash Nayak", "phone_number": "9438012345", "email": None},
    {"full_name": "Sasmita Behera", "phone_number": "8895632100", "email": "sasmita.b@email.com"},
    {"full_name": "Manoj Senapati", "phone_number": "9040123456", "email": None},
    {"full_name": "Deepa Mishra", "phone_number": "9178456321", "email": "deepa.m@email.com"},
    {"full_name": "Ramesh Tripathi", "phone_number": "8658904321", "email": None},
    {"full_name": "Suchitra Rath", "phone_number": "9777623456", "email": "suchitra.r@email.com"},
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_time(t: str) -> time:
    h, m = map(int, t.split(":"))
    return time(h, m)


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


async def get_or_none(db: AsyncSession, model, **kwargs):
    """Return first matching row or None."""
    from sqlalchemy import and_
    conditions = [getattr(model, k) == v for k, v in kwargs.items()]
    result = await db.execute(select(model).where(and_(*conditions)))
    return result.scalar_one_or_none()


# ── Seed phases ────────────────────────────────────────────────────────────────

async def seed_clinic(db: AsyncSession) -> Clinic:
    existing = await get_or_none(db, Clinic, name=UTKAL_HOSPITAL["name"])
    if existing:
        logger.info("clinic_already_exists", clinic_id=str(existing.id))
        return existing

    clinic = Clinic(**UTKAL_HOSPITAL)
    db.add(clinic)
    await db.flush()
    logger.info("clinic_created", clinic_id=str(clinic.id), name=clinic.name)
    return clinic


async def seed_departments(db: AsyncSession, clinic: Clinic) -> dict[str, Department]:
    rows = load_csv(CSV_DEPARTMENTS)
    dept_map: dict[str, Department] = {}

    for row in rows:
        name = row["name"].strip()
        existing = await get_or_none(db, Department, clinic_id=clinic.id, name=name)
        if existing:
            dept_map[name] = existing
            continue

        dept = Department(clinic_id=clinic.id, name=name)
        db.add(dept)
        await db.flush()
        dept_map[name] = dept
        logger.info("department_created", name=name)

    return dept_map


async def seed_doctors(
    db: AsyncSession,
    clinic: Clinic,
    dept_map: dict[str, Department],
) -> dict[str, Doctor]:
    rows = load_csv(CSV_DOCTORS)

    dept_id_map = {
        "1": "Neurology",
        "2": "Endocrinology",
        "3": "Dentistry",
        "4": "Physiotherapy",
    }

    doctor_map: dict[str, Doctor] = {}
    for row in rows:
        name = row["name"].strip()
        dept_name = dept_id_map.get(row["department_id"].strip(), "")
        dept = dept_map.get(dept_name)
        qualification = row.get("qualification", "").strip()

        existing = await get_or_none(db, Doctor, clinic_id=clinic.id, name=name)
        if existing:
            doctor_map[name] = existing
            continue

        doctor = Doctor(
            clinic_id=clinic.id,
            department_id=dept.id if dept else None,
            name=name,
            qualification=qualification,
            active=True,
        )
        db.add(doctor)
        await db.flush()
        doctor_map[name] = doctor
        logger.info("doctor_created", name=name, dept=dept_name)

    return doctor_map


async def seed_schedules(
    db: AsyncSession,
    doctor_map: dict[str, Doctor],
) -> None:
    for doctor_name, schedule_blocks in DOCTOR_SCHEDULES.items():
        doctor = doctor_map.get(doctor_name)
        if not doctor:
            logger.warning("doctor_not_found_for_schedule", name=doctor_name)
            continue

        for block in schedule_blocks:
            for day in block["days"]:
                existing = await get_or_none(
                    db,
                    WeeklySchedule,
                    doctor_id=doctor.id,
                    day_of_week=day,
                    start_time=parse_time(block["start"]),
                )
                if existing:
                    continue

                schedule = WeeklySchedule(
                    doctor_id=doctor.id,
                    day_of_week=day,
                    start_time=parse_time(block["start"]),
                    end_time=parse_time(block["end"]),
                    slot_duration_minutes=block["duration"],
                    is_active=True,
                )
                db.add(schedule)

        await db.flush()
        logger.info("schedules_seeded", doctor=doctor_name)


async def seed_slots(db: AsyncSession, clinic: Clinic, days: int = 30) -> dict[str, int]:
    """Generate concrete DoctorSlot rows from weekly schedules."""
    from app.services.slot_generator import generate_slots_for_clinic
    from app.utils.time_utils import now_ist

    summary = await generate_slots_for_clinic(
        db,
        clinic_id=clinic.id,
        start_date=now_ist().date(),
        days=days,
    )
    total = sum(summary.values())
    logger.info("slots_generated", total=total, by_doctor=summary)
    return summary


async def seed_patients(db: AsyncSession) -> list[Patient]:
    patients: list[Patient] = []
    for data in SAMPLE_PATIENTS:
        existing = await get_or_none(db, Patient, phone_number=data["phone_number"])
        if existing:
            patients.append(existing)
            continue

        p = Patient(**data)
        db.add(p)
        await db.flush()
        patients.append(p)
        logger.info("patient_created", name=data["full_name"])

    return patients


async def seed_appointments(
    db: AsyncSession,
    clinic: Clinic,
    doctor_map: dict[str, Doctor],
    patients: list[Patient],
) -> None:
    """
    Create 15 sample appointments using real available slots.
    Spreads appointments across different doctors, patients, and dates.
    """
    import pytz
    from sqlalchemy import and_
    IST = pytz.timezone("Asia/Kolkata")

    # Get available slots for each doctor (take first few)
    appt_configs = [
        ("Dr. Amitav Rath", patients[0], "new_consultation"),
        ("Dr. Amitav Rath", patients[1], "follow_up"),
        ("Dr. Akash Gupta", patients[2], "new_consultation"),
        ("Dr. Akash Gupta", patients[3], "review"),
        ("Dr. Madhusmita Sahu", patients[4], "new_consultation"),
        ("Dr. Madhusmita Sahu", patients[5], "follow_up"),
        ("Dr. Dibyalochan Swain", patients[6], "new_consultation"),
        ("Dr. Dibyalochan Swain", patients[7], "follow_up"),
        ("Dr. Mithilesh Kumar", patients[8], "new_consultation"),
        ("Dr. Mithilesh Kumar", patients[9], "follow_up"),
        ("Dr. Mukesh Kumar", patients[0], "new_consultation"),
        ("Dr. Mukesh Kumar", patients[1], "review"),
        ("Dr. Amitav Rath", patients[2], "new_consultation"),
        ("Dr. Madhusmita Sahu", patients[3], "follow_up"),
        ("Dr. Dibyalochan Swain", patients[4], "review"),
    ]

    created = 0
    for doctor_name, patient, appt_type in appt_configs:
        doctor = doctor_map.get(doctor_name)
        if not doctor:
            continue

        # Find a free slot for this doctor
        slot_result = await db.execute(
            select(DoctorSlot)
            .where(
                and_(
                    DoctorSlot.doctor_id == doctor.id,
                    DoctorSlot.slot_status == SlotStatus.AVAILABLE,
                    DoctorSlot.start_time > datetime.now(pytz.UTC),
                )
            )
            .order_by(DoctorSlot.start_time)
            .limit(1)
        )
        slot = slot_result.scalar_one_or_none()

        if slot is None:
            logger.warning("no_slot_available", doctor=doctor_name)
            continue

        # Check if appointment already exists for this slot
        existing_appt = await get_or_none(db, Appointment, slot_id=slot.id)
        if existing_appt:
            continue

        appt = Appointment(
            clinic_id=clinic.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            slot_id=slot.id,
            appointment_type=appt_type,
            status=AppointmentStatus.BOOKED,
            booking_source=BookingSource.ADMIN,
            reason="Sample appointment — seeded for demo.",
        )
        db.add(appt)
        slot.slot_status = SlotStatus.BOOKED
        await db.flush()
        created += 1

    logger.info("appointments_seeded", count=created)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        print("\n" + "=" * 60)
        print("  ClinicOS Voice --- Utkal Hospital Seed Script")
        print("=" * 60)

        # Phase 1: Clinic
        print("\n[1/7] Seeding clinic...")
        clinic = await seed_clinic(db)
        print(f"      - {clinic.name} (id: {clinic.id})")

        # Phase 2: Departments
        print("\n[2/7] Seeding departments...")
        dept_map = await seed_departments(db, clinic)
        for name in dept_map:
            print(f"      - {name}")

        # Phase 3: Doctors
        print("\n[3/7] Seeding doctors...")
        doctor_map = await seed_doctors(db, clinic, dept_map)
        for name in doctor_map:
            print(f"      - {name}")

        # Phase 4: Weekly Schedules
        print("\n[4/7] Seeding weekly schedules...")
        await seed_schedules(db, doctor_map)
        print(f"      - {len(DOCTOR_SCHEDULES)} doctors scheduled")

        await db.commit()

        # Phase 5: Slots (needs committed schedules)
        print(f"\n[5/7] Generating slots ({settings.SLOT_GENERATION_DAYS} days)...")
        slot_summary = await seed_slots(db, clinic, days=settings.SLOT_GENERATION_DAYS)
        total_slots = sum(slot_summary.values())
        for doctor_name, count in slot_summary.items():
            print(f"      - {doctor_name}: {count} slots")
        print(f"      Total: {total_slots} slots created")

        await db.commit()

        # Phase 6: Sample Patients
        print("\n[6/7] Seeding sample patients...")
        patients = await seed_patients(db)
        print(f"      - {len(patients)} patients")

        await db.commit()

        # Phase 7: Sample Appointments
        print("\n[7/7] Seeding sample appointments...")
        await seed_appointments(db, clinic, doctor_map, patients)

        await db.commit()

        print("\n" + "=" * 60)
        print("  Seed complete!")
        print(f"  CLINIC_ID={clinic.id}")
        print("  Add CLINIC_ID to your .env file.")
        print("=" * 60 + "\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
