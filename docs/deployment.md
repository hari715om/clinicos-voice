# Deployment Guide — ClinicOS Voice

## Architecture Overview

```
Internet → LiveKit Cloud (voice) → FastAPI on Render → Supabase PostgreSQL
                                 → Next.js on Vercel (admin dashboard)
```

---

## Backend Deployment — Render

### 1. Create a `render.yaml`

```yaml
services:
  - type: web
    name: clinicos-voice-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false     # Set in Render dashboard
      - key: GROQ_API_KEY
        sync: false
      - key: LIVEKIT_API_KEY
        sync: false
      - key: LIVEKIT_API_SECRET
        sync: false
      - key: CLINIC_ID
        sync: false
      - key: ADMIN_API_KEY
        sync: false
      - key: ENVIRONMENT
        value: production
      - key: PYTHONUTF8
        value: "1"
```

### 2. Deploy Steps

```bash
# From repo root
git add .
git commit -m "Deploy ClinicOS Voice backend"
git push origin main

# Then in Render dashboard:
# New → Web Service → Connect GitHub → Select clinicos-voice repo
# Set root directory: backend/
# Set all env vars from your .env
```

### 3. Run Migrations on Render

After deploy, open Render Shell and run:
```bash
alembic upgrade head
python scripts/seed_clinic.py
```

---

## Frontend Deployment — Vercel

```bash
cd frontend
npx vercel --prod
# Set NEXT_PUBLIC_API_URL=https://clinicos-voice-api.onrender.com
```

---

## Environment Variables Checklist

| Variable | Where to get |
|---|---|
| `DATABASE_URL` | Supabase → Settings → Database → Pooled URL |
| `DATABASE_URL_SYNC` | Supabase → Direct URL (for Alembic only) |
| `GROQ_API_KEY` | https://console.groq.com |
| `LIVEKIT_URL` | LiveKit Cloud → Project → Settings |
| `LIVEKIT_API_KEY` | LiveKit Cloud → Keys |
| `LIVEKIT_API_SECRET` | LiveKit Cloud → Keys |
| `CLINIC_ID` | Printed by `seed_clinic.py` |
| `ADMIN_API_KEY` | Generate: `openssl rand -hex 32` |

---

## Health Check

After deployment, verify:
```bash
curl https://clinicos-voice-api.onrender.com/health
# {"status":"healthy","app":"ClinicOS Voice","version":"1.0.0","environment":"production"}
```
