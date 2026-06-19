"""
ClinicOS Voice — FastAPI Application Entry Point.

Architecture:
- Lifespan context manager handles startup/shutdown (logging, DB pool warm-up).
- All routes are mounted under /api/v1/.
- Domain exceptions are mapped to HTTP errors via exception handlers.
- Health check at / for container orchestration.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    AppointmentNotReschedulableError,
    ClinicNotFoundError,
    ConflictError,
    DoctorNotFoundError,
    InvalidDateError,
    PatientNotFoundError,
    SlotNotAvailableError,
    SlotNotFoundError,
)
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs once on startup and shutdown."""
    configure_logging()
    logger.info(
        "clinicos_voice_starting",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    yield
    logger.info("clinicos_voice_shutdown")


# ── App factory ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "ClinicOS Voice — Production-grade healthcare voice receptionist API. "
        "Powers the LiveKit voice agent for Utkal Hospital."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Domain exception handlers ─────────────────────────────────────────────────
def _domain_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )
    return handler


app.add_exception_handler(SlotNotFoundError, _domain_handler(404))
app.add_exception_handler(AppointmentNotFoundError, _domain_handler(404))
app.add_exception_handler(ClinicNotFoundError, _domain_handler(404))
app.add_exception_handler(DoctorNotFoundError, _domain_handler(404))
app.add_exception_handler(PatientNotFoundError, _domain_handler(404))
app.add_exception_handler(SlotNotAvailableError, _domain_handler(409))
app.add_exception_handler(ConflictError, _domain_handler(409))
app.add_exception_handler(AppointmentAlreadyCancelledError, _domain_handler(409))
app.add_exception_handler(AppointmentNotReschedulableError, _domain_handler(422))
app.add_exception_handler(InvalidDateError, _domain_handler(422))


# ── Route registration ─────────────────────────────────────────────────────────
from app.api.v1.routes import (  # noqa: E402 — import after app creation
    appointments,
    availability,
    calls,
    clinics,
    doctors,
    evals,
    admin,
)

API_PREFIX = "/api/v1"
app.include_router(clinics.router, prefix=API_PREFIX, tags=["Clinics"])
app.include_router(doctors.router, prefix=API_PREFIX, tags=["Doctors"])
app.include_router(availability.router, prefix=API_PREFIX, tags=["Availability"])
app.include_router(appointments.router, prefix=API_PREFIX, tags=["Appointments"])
app.include_router(calls.router, prefix=API_PREFIX, tags=["Calls"])
app.include_router(evals.router, prefix=API_PREFIX, tags=["Evals"])
app.include_router(admin.router, prefix=API_PREFIX, tags=["Admin"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Lightweight health check for container orchestration / Render."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    return {"message": f"Welcome to {settings.APP_NAME} API. See /docs for endpoints."}
