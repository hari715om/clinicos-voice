# ClinicOS Voice
### Production-grade Healthcare Voice Receptionist — Utkal Hospital

> **ClinicOS Voice** is a real-time voice receptionist that lets patients book, reschedule, and cancel appointments with Utkal Hospital by speaking naturally. It uses LiveKit for voice orchestration, FastAPI for backend logic, and Groq LLaMA-3 for language understanding.

---

## 1. Overview

A patient calls the hospital number. ClinicOS Voice answers, greets them naturally, and handles their scheduling request end-to-end — all backed by a real PostgreSQL database. No hallucination. Every slot check, booking, and cancellation is a real API call.

**Supported flows:**
- New appointment booking
- Appointment rescheduling  
- Appointment cancellation
- Slot availability queries
- Conflict detection and alternative suggestion
- Mid-conversation intent changes

---

## 2. Architecture

```
Patient Phone → LiveKit SIP → LiveKit Room
                                    │
                            VoicePipelineAgent
                          ┌──────────────────┐
                          │  STT: Deepgram   │
                          │  LLM: Groq       │
                          │  TTS: ElevenLabs │
                          └──────────────────┘
                                    │ tool calls
                                    ▼
                          FastAPI Backend (8000)
                          ┌──────────────────────────┐
                          │ /api/v1/availability      │
                          │ /api/v1/appointments      │
                          │ /api/v1/calls             │
                          └──────────────────────────┘
                                    │
                          PostgreSQL (Neon/Render)
                          + Redis (optional holds)
```

---

## 3. Stack

| Layer | Technology |
|---|---|
| Voice | LiveKit Agents |
| STT | Deepgram Nova-2 |
| LLM | Groq `llama-3.3-70b-versatile` |
| TTS | ElevenLabs |
| Backend | FastAPI (async) |
| ORM | SQLAlchemy 2.0 |
| DB | PostgreSQL (Neon) |
| Cache | Redis (optional) |
| Frontend | Next.js (minimal admin) |
| Deploy | Render + Vercel |

---

## 5. How to Run Locally

### Prerequisites
- Python 3.11+
- Docker + Docker Compose (for PostgreSQL + Redis)
- LiveKit Cloud project (for voice calls)
- Groq API key

### Steps

```bash
# 1. Start the database stack
docker-compose -f infra/docker-compose.yml up -d postgres redis

# 2. Set up Python environment
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, GROQ_API_KEY, LIVEKIT_* credentials

# 4. Run database migrations
alembic upgrade head

# 5. Seed Utkal Hospital data
python scripts/seed_clinic.py
# Copy the printed CLINIC_ID into your .env

# 6. Start the API server
uvicorn app.main:app --reload --port 8000

# 7. Browse the API
open http://localhost:8000/docs

# 8. Start the voice agent (Phase 3)
python -m app.agents.livekit_agent
```

---

## 6. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/clinics/{id}` | Clinic details |
| GET | `/api/v1/clinics/{id}/doctors` | List doctors |
| GET | `/api/v1/availability` | Available slots |
| POST | `/api/v1/appointments` | Book appointment |
| PATCH | `/api/v1/appointments/{id}` | Reschedule |
| DELETE | `/api/v1/appointments/{id}` | Cancel |
| GET | `/api/v1/patients/{phone}/appointments` | Patient history |
| POST | `/api/v1/calls/start` | Start call session |
| POST | `/api/v1/evals/run` | Run eval harness |

Full docs: `http://localhost:8000/docs`

---

## 7. Eval Harness

```bash
cd eval
python runners/call_runner.py --dataset booking_cases
```

Produces `eval/results/latest_report.json` with:
- Task success rate
- Correct tool-call rate  
- Conflict handling success
- Hallucination count
- Average turns to completion
- Average latency

**Test categories:** booking (5 cases), rescheduling (3), cancellation (3), conflicts (4)

---

## 8. Deployment

- **Backend**: Render (Docker, auto-deploy from GitHub)
- **Database**: Neon PostgreSQL (serverless)
- **Redis**: Render Redis (optional)
- **Frontend**: Vercel (Next.js)
- **Voice**: LiveKit Cloud

---

## 9. Known Limitations

- Single clinic scope (Utkal Hospital only)
- No multilingual support
- No payment processing
- No insurance verification
- Slot window limited to 30 days ahead

---

## 10. Future Improvements

- Multi-clinic support
- SMS/WhatsApp appointment confirmations
- Doctor-side admin dashboard
- Automated daily slot regeneration
- Patient identity verification via OTP
