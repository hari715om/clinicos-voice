"""
Domain exceptions for ClinicOS Voice.

All service-layer errors extend ClinicOSError so route handlers can catch
them with a single except clause and return appropriate HTTP responses.
"""
from __future__ import annotations


class ClinicOSError(Exception):
    """Base exception for all ClinicOS Voice domain errors."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail or message
        super().__init__(message)


# ── Slot / Scheduling Errors ───────────────────────────────────────────────────

class SlotNotFoundError(ClinicOSError):
    """The requested slot ID does not exist."""


class SlotNotAvailableError(ClinicOSError):
    """
    The slot is in a non-bookable state (HELD, BOOKED, or BLOCKED).
    Always include which state the slot is in.
    """


class SlotHoldExpiredError(ClinicOSError):
    """A hold that was placed on a slot has expired; must re-check availability."""


class ConflictError(ClinicOSError):
    """A scheduling conflict was detected (double-booking prevention)."""


# ── Appointment Errors ────────────────────────────────────────────────────────

class AppointmentNotFoundError(ClinicOSError):
    """No appointment found for the given ID or criteria."""


class AppointmentAlreadyCancelledError(ClinicOSError):
    """Attempt to cancel an appointment that is already cancelled."""


class AppointmentNotReschedulableError(ClinicOSError):
    """Appointment cannot be rescheduled (e.g. cancelled, completed, or within MIN_RESCHEDULE_HOURS)."""


# ── Patient Errors ────────────────────────────────────────────────────────────

class PatientNotFoundError(ClinicOSError):
    """No patient found for the given criteria."""


# ── Clinic / Doctor Errors ────────────────────────────────────────────────────

class ClinicNotFoundError(ClinicOSError):
    """The referenced clinic ID does not exist."""


class DoctorNotFoundError(ClinicOSError):
    """The referenced doctor ID does not exist or is inactive."""


class DepartmentNotFoundError(ClinicOSError):
    """The referenced department ID does not exist."""


# ── Validation Errors ─────────────────────────────────────────────────────────

class InvalidDateError(ClinicOSError):
    """A provided date is invalid, in the past, or exceeds the advance booking window."""


class InvalidPhoneNumberError(ClinicOSError):
    """A phone number is malformed or does not meet the validation rules."""
