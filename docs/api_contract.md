# API Contract — ClinicOS Voice

All endpoints are under `/api/v1/`. The API is documented interactively at `/docs`.

## Authentication

Admin endpoints require the `X-Admin-API-Key` header.
Voice agent tool calls are made server-to-server (no auth required from agent side for now).

## Core Endpoints

### Availability
```
GET /api/v1/availability
  ?clinic_id=<uuid>
  &date=2026-06-20          # YYYY-MM-DD (required)
  &doctor_id=<uuid>         # optional
  &department_id=<uuid>     # optional
  &appointment_type=new_consultation

Response:
{
  "date": "2026-06-20",
  "clinic_id": "...",
  "doctor_id": null,
  "available_slots": [...],
  "total_available": 12,
  "nearest_alternatives": []  # populated when total_available=0
}
```

### Book Appointment
```
POST /api/v1/appointments
Content-Type: application/json

{
  "clinic_id": "...",
  "patient_name": "Rajesh Mohanty",
  "phone_number": "9861234567",
  "doctor_id": "...",
  "slot_id": "...",
  "appointment_type": "new_consultation",
  "reason": "First visit",
  "booking_source": "voice_agent"
}

Response 201:
{
  "id": "...",
  "status": "booked",
  ...
}

Error 409: SlotNotAvailableError — slot was taken between check and commit
```

### Reschedule
```
PATCH /api/v1/appointments/{appointment_id}
{
  "new_slot_id": "...",
  "reason": "Cannot make original time"
}

Response 200: new appointment record
Error 422: within MIN_RESCHEDULE_HOURS window
Error 409: new slot unavailable
```

### Cancel
```
DELETE /api/v1/appointments/{appointment_id}
{
  "reason": "Patient request"
}

Response 200: cancelled appointment record
Error 409: already cancelled
```

## Error Format

All domain errors return:
```json
{
  "error": "SlotNotAvailableError",
  "detail": "Slot abc123 is booked and cannot be booked."
}
```
