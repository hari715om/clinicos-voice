"""
Alembic environment configuration for ClinicOS Voice.

Uses the SYNCHRONOUS PostgreSQL URL (psycopg2) for migrations.
All models are imported here so that autogenerate detects all tables.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add backend/ to sys.path so `app` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import all models (CRITICAL for autogenerate) ──────────────────────────────
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402 — triggers all model imports via __init__.py

# ── Alembic config ─────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use DB URL from environment (falls back to DATABASE_URL_SYNC env var)
from app.core.config import settings  # noqa: E402

_db_url = settings.DATABASE_URL_SYNC or settings.DATABASE_URL.replace(
    "postgresql+asyncpg", "postgresql+psycopg2"
)
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


# ── Migration helpers ──────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection, outputs SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=False,  # Disabled: Windows tzdata incompatibility
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,  # Disabled: Windows tzdata incompatibility
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
