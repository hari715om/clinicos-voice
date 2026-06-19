# Supabase Setup Guide — ClinicOS Voice

## Why Supabase?

Supabase gives you a production PostgreSQL database with:
- Auto-backups + point-in-time recovery
- Connection pooling via PgBouncer (critical for serverless)
- Built-in SSL
- Free tier: 500MB DB, 2 projects
- Upgrade path to $25/mo for production

---

## Step 1 — Create a Supabase Project

1. Go to **https://supabase.com** → **New Project**
2. Choose a region closest to your users (e.g. `ap-south-1` for India)
3. Set a strong database password — **save this, you'll need it**
4. Wait ~2 minutes for provisioning

---

## Step 2 — Get Your Connection Strings

In your Supabase project:

1. Go to **Settings → Database**
2. Scroll to **Connection string**
3. Select **URI** tab

You'll see two connection modes:

### Direct Connection (for migrations)
```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### Pooled Connection (for app runtime — use this in FastAPI)
```
postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

> [!IMPORTANT]
> Use the **pooled** URL for FastAPI runtime. Use the **direct** URL only for Alembic migrations. Supabase's pooler does not support `PREPARE` statements which Alembic uses.

---

## Step 3 — Update your `.env`

```bash
# Async URL for FastAPI (pooled — note: use asyncpg driver)
DATABASE_URL=postgresql+asyncpg://postgres.YOUR_REF:YOUR_PASS@aws-0-ap-south-1.pooler.supabase.com:6543/postgres

# Sync URL for Alembic ONLY — use direct connection (no pooler)
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:YOUR_PASS@db.YOUR_REF.supabase.co:5432/postgres
```

> [!WARNING]
> Supabase pooled connections require `?sslmode=require` — asyncpg enables SSL by default when connecting to Supabase, but if you get SSL errors add `?ssl=require` to the URL.

---

## Step 4 — Create the `clinicos` Role

Run this in the Supabase **SQL Editor** (Dashboard → SQL Editor → New Query):

```sql
-- Create app user with limited privileges
CREATE ROLE clinicos WITH LOGIN PASSWORD 'your_strong_password_here';
GRANT USAGE ON SCHEMA public TO clinicos;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO clinicos;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO clinicos;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO clinicos;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO clinicos;
```

Then update your `DATABASE_URL` to use `clinicos` instead of `postgres`.

---

## Step 5 — Run Migrations Against Supabase

```bash
# From backend/
venv\Scripts\alembic upgrade head
```

This uses `DATABASE_URL_SYNC` (direct connection) to create all 11 tables.

Check the result in Supabase Dashboard → **Table Editor** — you should see:
`clinics, departments, doctors, weekly_schedules, doctor_slots, patients, appointments, call_sessions, call_events, eval_runs, eval_cases`

---

## Step 6 — Seed Utkal Hospital Data

```bash
venv\Scripts\python scripts/seed_clinic.py
```

Copy the printed `CLINIC_ID` and add it to your `.env`:
```bash
CLINIC_ID=<printed-uuid>
```

---

## Step 7 — Verify Connection

```bash
venv\Scripts\uvicorn app.main:app --reload --port 8000
# Then:
curl http://localhost:8000/api/v1/clinics/<CLINIC_ID>
```

---

## Connection Pooling Notes

Supabase uses **PgBouncer in transaction mode** for pooled connections.

**Implications for ClinicOS Voice:**
- `SELECT FOR UPDATE` (used in slot locking) works in transaction mode ✅
- Prepared statements are **disabled** in transaction mode — this affects Alembic only (use direct URL)
- Max pool size: set `pool_size=5, max_overflow=10` in SQLAlchemy for Supabase free tier

Add to `app/db/session.py` for production:
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # detect stale connections
    pool_recycle=300,      # recycle every 5 min
)
```

---

## Environment Variables Summary

| Variable | Local Dev | Supabase Production |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://clinicos:secret@localhost:5432/clinicos_voice` | `postgresql+asyncpg://postgres.REF:PASS@pooler.supabase.com:6543/postgres` |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://postgres:hariom_715@localhost:5432/clinicos_voice` | `postgresql+psycopg2://postgres:PASS@db.REF.supabase.co:5432/postgres` |

---

## Free Tier Limits

| Resource | Limit |
|---|---|
| Database size | 500 MB |
| Monthly active users | 50,000 |
| Bandwidth | 5 GB |
| Projects | 2 free |
| Pauses after | 7 days inactivity |

> [!TIP]
> To prevent the free tier project from pausing, set up a cron job or use **Uptime Robot** to ping your API health endpoint every 5 minutes.
