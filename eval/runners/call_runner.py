"""
Eval Runner — executes test cases against the live FastAPI and produces a JSON report.

Usage:
    python -m eval.runners.call_runner --dataset all
    python -m eval.runners.call_runner --dataset booking

Output:
    eval/results/latest_report.json
    eval/results/<timestamp>_<datasets>.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = REPO_ROOT / "eval" / "datasets"
RESULTS_DIR  = REPO_ROOT / "eval" / "results"
RESULTS_DIR.mkdir(exist_ok=True)

BASE_URL = "http://localhost:8000/api/v1"

DATASET_FILES = {
    "booking":      "booking_cases.json",
    "reschedule":   "reschedule_cases.json",
    "cancellation": "cancellation_cases.json",
    "conflict":     "conflict_cases.json",
}


def load_dataset(name: str) -> list[dict]:
    """Load a dataset JSON file, skipping any leading Python docstring."""
    path = DATASETS_DIR / DATASET_FILES[name]
    with open(path, encoding="utf-8") as f:
        content = f.read()
    start = content.find("[")
    if start == -1:
        raise ValueError(f"No JSON array found in {path}")
    return json.loads(content[start:])


def read_clinic_id() -> str:
    """Read CLINIC_ID from backend/.env."""
    env_path = REPO_ROOT / "backend" / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CLINIC_ID="):
            val = line.split("=", 1)[1].strip()
            if val:
                return val
    raise RuntimeError("CLINIC_ID not set in backend/.env — run seed_clinic.py first")


# Global slot cache to ensure unique slots across cases
_CLINIC_SLOTS_CACHE: dict[str, list[dict]] = {}

async def get_available_slots(client: httpx.AsyncClient, clinic_id: str, count: int) -> list[dict]:
    """Get unique available slots, fetching from API if cache is empty."""
    if clinic_id not in _CLINIC_SLOTS_CACHE:
        _CLINIC_SLOTS_CACHE[clinic_id] = []
        check = datetime.now(timezone.utc) + timedelta(days=2)
        for _ in range(14):
            date_str = check.strftime("%Y-%m-%d")
            r = await client.get(f"{BASE_URL}/availability", params={"clinic_id": clinic_id, "date": date_str})
            slots = r.json().get("available_slots", [])
            _CLINIC_SLOTS_CACHE[clinic_id].extend(slots)
            check += timedelta(days=1)
            
    # Pop unique slots from the cache
    slots = []
    for _ in range(count):
        if _CLINIC_SLOTS_CACHE[clinic_id]:
            slots.append(_CLINIC_SLOTS_CACHE[clinic_id].pop(0))
    return slots


async def prebook(
    client: httpx.AsyncClient,
    clinic_id: str,
    doctor_id: str,
    slot_id: str,
    phone: str,
    case_id: str,
) -> Optional[str]:
    """Pre-book a slot and return the appointment ID, or None on failure."""
    r = await client.post(f"{BASE_URL}/appointments", json={
        "clinic_id":        clinic_id,
        "patient_name":     "Eval Pre-book Patient",
        "phone_number":     phone,
        "doctor_id":        doctor_id,
        "slot_id":          slot_id,
        "appointment_type": "new_consultation",
        "reason":           f"Pre-book for eval case {case_id}",
        "booking_source":   "admin",
    })
    if r.status_code in (200, 201):
        return r.json().get("id")
    return None


def extract_phone(case: dict) -> str:
    """Extract first 10-digit number from case utterances."""
    for u in case.get("input_utterances", []):
        digits = "".join(c for c in u if c.isdigit())
        if len(digits) == 10:
            return digits
    return "8000099001"


async def run_case(client: httpx.AsyncClient, case: dict, clinic_id: str) -> dict:
    """
    Execute a single test case against the live API.

    Strategy by case_type:
      booking      → find slot → book → verify created
      rescheduling → pre-book slot[0] → reschedule to slot[1]
      cancellation → pre-book slot[0] → cancel it
      conflict     → pre-book slot[0] → attempt to re-book same slot → expect 409/422 = PASS
    """
    result: dict = {
        "case_id":     case["case_id"],
        "case_type":   case["case_type"],
        "description": case["description"],
        "tags":        case.get("tags", []),
        "tool_results": [],
        "outcome":     None,
        "passed":      False,
        "error":       None,
        "latency_ms":  0,
    }
    t_start = time.monotonic()

    try:
        case_type        = case["case_type"]
        expected_outcome = case.get("expected_outcome", {})
        expected_action  = expected_outcome.get("action", "")
        phone            = extract_phone(case)

        # ── Fetch available slots ────────────────────────────────────────────
        slots = await get_available_slots(client, clinic_id, 2)
        date_str = slots[0]["start_time"][:10] if slots else datetime.now().strftime("%Y-%m-%d")

        if not slots and case_type in ("booking", "rescheduling", "cancellation", "conflict"):
            result["error"] = "No available slots in next 14 days — re-run scripts/seed_clinic.py"
            return result

        slot0     = slots[0] if slots else None
        slot1     = slots[1] if len(slots) > 1 else slots[0] if slots else None
        doctor_id = slot0["doctor_id"] if slot0 else None
        slot0_id  = slot0["id"] if slot0 else None
        slot1_id  = slot1["id"] if slot1 else None

        # ── Pre-book for cancel/reschedule/conflict cases ────────────────────
        if case_type in ("cancellation", "rescheduling", "conflict") and slot0_id:
            appt_id = await prebook(client, clinic_id, doctor_id, slot0_id, phone, case["case_id"])
            if not appt_id:
                result["error"] = "Pre-booking failed — cannot proceed with test"
                return result
            result["booked_appointment_id"] = appt_id
            # For conflict cases: slot0 is now booked — we'll try to re-book it
            # For reschedule/cancel: slot0 is booked; use slot1 as the target

        # ── Execute expected tool calls ──────────────────────────────────────
        for expected_tool in case.get("expected_tool_calls", []):
            tool_name = expected_tool["tool"]
            tr: dict  = {"tool": tool_name, "status": None, "latency_ms": 0, "response": None}
            t0 = time.monotonic()

            # ── check_availability ──────────────────────────────────────────
            if tool_name == "check_availability":
                r = await client.get(
                    f"{BASE_URL}/availability",
                    params={"clinic_id": clinic_id, "date": date_str},
                )
                tr["status"]   = r.status_code
                tr["response"] = {"total_available": r.json().get("total_available")}

            # ── get_doctor_list ─────────────────────────────────────────────
            elif tool_name == "get_doctor_list":
                dept = expected_tool.get("args", {}).get("department", "")
                r = await client.get(
                    f"{BASE_URL}/clinics/{clinic_id}/doctors",
                    params={"department_name": dept} if dept else {},
                )
                tr["status"]   = r.status_code
                tr["response"] = {"count": len(r.json())}

            # ── book_appointment ────────────────────────────────────────────
            elif tool_name == "book_appointment":
                if case_type == "conflict":
                    # Intentionally try to re-book the already-booked slot0
                    target_slot = slot0_id
                else:
                    target_slot = slot1_id  # use a fresh slot for regular booking
                    # But for plain booking cases, there was no pre-book, so slot0 is free
                    if case_type == "booking":
                        target_slot = slot0_id

                r = await client.post(f"{BASE_URL}/appointments", json={
                    "clinic_id":        clinic_id,
                    "patient_name":     "Eval Test Patient",
                    "phone_number":     phone,
                    "doctor_id":        doctor_id,
                    "slot_id":          target_slot,
                    "appointment_type": expected_tool.get("args", {}).get(
                                            "appointment_type", "new_consultation"),
                    "reason":           f"Eval case {case['case_id']}",
                    "booking_source":   "admin",
                })
                tr["status"] = r.status_code
                if r.status_code in (200, 201):
                    appt = r.json()
                    result["booked_appointment_id"] = appt.get("id")
                    tr["response"] = {"status": appt.get("status"), "id": appt.get("id")}
                else:
                    tr["response"] = {"error_code": r.status_code, "detail": r.text[:200]}

            # ── lookup_patient_appointments ─────────────────────────────────
            elif tool_name == "lookup_patient_appointments":
                r = await client.get(f"{BASE_URL}/patients/{phone}/appointments")
                tr["status"]   = r.status_code
                tr["response"] = {"count": len(r.json())}

            # ── reschedule_appointment ──────────────────────────────────────
            elif tool_name == "reschedule_appointment":
                appt_id = result.get("booked_appointment_id")
                if appt_id and slot1_id:
                    r = await client.patch(
                        f"{BASE_URL}/appointments/{appt_id}",
                        json={"new_slot_id": slot1_id, "reason": "eval reschedule"},
                    )
                    tr["status"]   = r.status_code
                    tr["response"] = r.json() if r.status_code == 200 else r.text[:200]
                else:
                    tr["status"]   = -1
                    tr["response"] = "no pre-booked appointment to reschedule"

            # ── cancel_appointment ──────────────────────────────────────────
            elif tool_name == "cancel_appointment":
                appt_id = result.get("booked_appointment_id")
                if appt_id:
                    # httpx delete() does not support 'json', use request() directly
                    r = await client.request(
                        "DELETE",
                        f"{BASE_URL}/appointments/{appt_id}",
                        json={"reason": "eval cancel"},
                    )
                    tr["status"]   = r.status_code
                    tr["response"] = (
                        {"status": r.json().get("status")} if r.status_code == 200
                        else {"error": r.text[:200]}
                    )
                else:
                    tr["status"]   = -1
                    tr["response"] = "no pre-booked appointment to cancel"

            tr["latency_ms"] = round((time.monotonic() - t0) * 1000)
            result["tool_results"].append(tr)

        # ── Determine pass/fail ──────────────────────────────────────────────
        if expected_action == "booked":
            result["passed"] = bool(result.get("booked_appointment_id"))

        elif expected_action == "rescheduled":
            rr = [t for t in result["tool_results"] if t["tool"] == "reschedule_appointment"]
            result["passed"] = bool(rr and rr[-1].get("status") == 200)

        elif expected_action == "cancelled":
            cr = [t for t in result["tool_results"] if t["tool"] == "cancel_appointment"]
            result["passed"] = bool(cr and cr[-1].get("status") == 200)

        elif expected_action == "no_booking":
            # PASS: the API should reject the duplicate/invalid booking
            br = [t for t in result["tool_results"] if t["tool"] == "book_appointment"]
            if br:
                result["passed"] = br[-1].get("status") in (400, 409, 422)
            else:
                # No booking attempted at all (e.g. availability check showed 0 slots)
                result["passed"] = True

        else:
            result["passed"] = all(
                t.get("status") in (200, 201) for t in result["tool_results"]
            )

        result["outcome"] = "pass" if result["passed"] else "fail"

    except Exception as exc:
        result["error"]   = f"{type(exc).__name__}: {exc}"
        result["outcome"] = "error"

    result["latency_ms"] = round((time.monotonic() - t_start) * 1000)
    return result


async def run_dataset(dataset_name: str, clinic_id: str) -> dict:
    cases   = load_dataset(dataset_name)
    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for case in cases:
            print(f"  [{case['case_id']}] {case['description'][:60]}...", end=" ", flush=True)
            res = await run_case(client, case, clinic_id)
            label = "PASS" if res["passed"] else ("ERROR" if res["error"] else "FAIL")
            print(f"{label} ({res['latency_ms']}ms)")
            results.append(res)

    passed = sum(1 for r in results if r["passed"])
    return {
        "dataset":   dataset_name,
        "total":     len(results),
        "passed":    passed,
        "failed":    len(results) - passed,
        "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
        "cases":     results,
    }


async def main(datasets: list[str]) -> None:
    # Health check
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.get("http://localhost:8000/health")
            r.raise_for_status()
        except Exception:
            print("ERROR: FastAPI server is not running on localhost:8000")
            print("  Start it with: uvicorn app.main:app --reload --port 8000")
            sys.exit(1)

    clinic_id = read_clinic_id()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    all_results: list[dict] = []

    print(f"\n=== ClinicOS Voice Eval Harness ===")
    print(f"Clinic: {clinic_id}")
    print(f"Server: http://localhost:8000\n")

    for ds_name in datasets:
        print(f"--- Dataset: {ds_name} ---")
        ds_result = await run_dataset(ds_name, clinic_id)
        all_results.append(ds_result)
        print(f"    Result: {ds_result['passed']}/{ds_result['total']} passed ({ds_result['pass_rate']}%)\n")

    total  = sum(r["total"]  for r in all_results)
    passed = sum(r["passed"] for r in all_results)
    report = {
        "run_at":       timestamp,
        "clinic_id":    clinic_id,
        "datasets_run": datasets,
        "summary": {
            "total":     total,
            "passed":    passed,
            "failed":    total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
        },
        "datasets": all_results,
    }

    latest_path = RESULTS_DIR / "latest_report.json"
    dated_path  = RESULTS_DIR / f"{timestamp}_{'_'.join(datasets)}.json"
    for path in (latest_path, dated_path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    print(f"=== Summary ===")
    print(f"  Total:     {total}")
    print(f"  Passed:    {passed}")
    print(f"  Failed:    {total - passed}")
    print(f"  Pass rate: {report['summary']['pass_rate']}%")
    print(f"\nReport: {latest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClinicOS Voice Eval Runner")
    parser.add_argument(
        "--dataset",
        choices=list(DATASET_FILES.keys()) + ["all"],
        default="all",
    )
    args = parser.parse_args()
    datasets = list(DATASET_FILES.keys()) if args.dataset == "all" else [args.dataset]
    asyncio.run(main(datasets))
