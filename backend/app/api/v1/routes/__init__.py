"""ClinicOS Voice — API v1 routes package."""
from app.api.v1.routes import (
    appointments,
    availability,
    calls,
    clinics,
    doctors,
    evals,
    admin,
)

__all__ = [
    "appointments",
    "availability",
    "calls",
    "clinics",
    "doctors",
    "evals",
    "admin",
]
