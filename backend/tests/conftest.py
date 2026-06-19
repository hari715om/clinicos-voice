"""
Test fixtures and async session setup for ClinicOS Voice tests.
Uses a dedicated PostgreSQL test database for production-faithful testing.
Database: clinicos_voice_test (must exist — run scripts/create_test_db.py once)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load .env before importing settings
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.constants import SlotStatus, AppointmentStatus, BookingSource
from app.db.base import Base
from app.models.clinic import Clinic, Department
from app.models.doctor import Doctor, WeeklySchedule
from app.models.slot import DoctorSlot
from app.models.patient import Patient
from app.models.appointment import Appointment
import app.models  # noqa: F401 — register all models

# clinicos_voice_test must already exist (created via psql as postgres superuser)
TEST_DATABASE_URL = settings.DATABASE_URL.replace("clinicos_voice", "clinicos_voice_test")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_schema():
    """Create all tables in test DB before the session, drop them after."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)   # clean slate
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a rolled-back session per test.
    Each test runs in isolation — nothing persists to the test DB.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def clinic(db: AsyncSession) -> Clinic:
    c = Clinic(name="Test Hospital", city="Bhubaneswar", timezone="Asia/Kolkata")
    db.add(c)
    await db.flush()
    return c


@pytest_asyncio.fixture
async def department(db: AsyncSession, clinic: Clinic) -> Department:
    d = Department(clinic_id=clinic.id, name="Neurology")
    db.add(d)
    await db.flush()
    return d


@pytest_asyncio.fixture
async def doctor(db: AsyncSession, clinic: Clinic, department: Department) -> Doctor:
    doc = Doctor(
        clinic_id=clinic.id,
        department_id=department.id,
        name="Dr. Test Doctor",
        qualification="MD",
        active=True,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest_asyncio.fixture
async def available_slot(db: AsyncSession, clinic: Clinic, doctor: Doctor) -> DoctorSlot:
    now = datetime.now(timezone.utc)
    slot = DoctorSlot(
        doctor_id=doctor.id,
        clinic_id=clinic.id,
        start_time=now + timedelta(days=1, hours=2),
        end_time=now + timedelta(days=1, hours=2, minutes=30),
        slot_status=SlotStatus.AVAILABLE,
    )
    db.add(slot)
    await db.flush()
    return slot


@pytest_asyncio.fixture
async def patient(db: AsyncSession) -> Patient:
    # Unique phone per test run prevents unique-constraint collisions on rollback edge cases
    p = Patient(
        full_name="Test Patient",
        phone_number=f"9{uuid.uuid4().int % 999999999:09d}",
    )
    db.add(p)
    await db.flush()
    return p
