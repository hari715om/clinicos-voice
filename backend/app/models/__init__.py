"""
Models package — aggregate import.

Importing all models here ensures SQLAlchemy's mapper registry is fully
populated before Alembic runs autogenerate. This file MUST be imported
in alembic/env.py before `target_metadata` is referenced.
"""
from app.models.clinic import Clinic, Department
from app.models.doctor import Doctor, WeeklySchedule
from app.models.slot import DoctorSlot
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.call_session import CallSession, CallEvent
from app.models.eval_run import EvalRun, EvalCase

__all__ = [
    # Clinic
    "Clinic",
    "Department",
    # Doctors
    "Doctor",
    "WeeklySchedule",
    # Slots
    "DoctorSlot",
    # Patients
    "Patient",
    # Appointments
    "Appointment",
    # Calls
    "CallSession",
    "CallEvent",
    # Eval
    "EvalRun",
    "EvalCase",
]
