"use client";

import { useEffect, useState } from "react";
import "./globals.css";

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface Clinic {
  id: string;
  name: string;
  address: string;
  city: string;
  timezone: string;
  business_hours: Record<string, string>;
}

interface Doctor {
  id: string;
  name: string;
  qualification: string | null;
  specialization: string | null;
  consultation_fee: number | null;
  department_id: string | null;
  active: boolean;
  weekly_schedules?: Schedule[];
  department_name?: string;
}

interface Schedule {
  id: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
}

interface Appointment {
  id: string;
  clinic_id: string;
  doctor_id: string;
  patient_id: string;
  slot_id: string;
  appointment_type: string;
  status: string;
  booking_source: string;
  reason: string | null;
  notes: string | null;
  cancelled_at: string | null;
  rescheduled_from_appointment_id: string | null;
  created_at: string;
  updated_at: string;
  patient_name: string | null;
  patient_phone: string | null;
  doctor_name: string | null;
  department_name: string | null;
  slot_start_time: string | null;
  slot_end_time: string | null;
}

interface Stats {
  doctors: number;
  patients: number;
  slots_total: number;
  appointments_total: number;
}

// â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CLINIC_ID = process.env.NEXT_PUBLIC_CLINIC_ID || "";
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || "change-this-before-deploy";

// â”€â”€ Icons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const Icon = {
  dashboard: (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
    </svg>
  ),
  appointments: (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  ),
  doctors: (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  agent: (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>
    </svg>
  ),
  refresh: (
    <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{width:12,height:12}}>
      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
};

// â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function initials(name: string): string {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "â€”";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
    });
  } catch { return iso; }
}

function fmtDate(iso: string | null): string {
  if (!iso) return "â€”";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "numeric", month: "short", year: "numeric"
    });
  } catch { return iso; }
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase();
  let cls = "badge badge-neutral";
  if (s === "booked") cls = "badge badge-booked";
  else if (s === "cancelled") cls = "badge badge-cancelled";
  else if (s === "rescheduled") cls = "badge badge-rescheduled";
  return <span className={cls}>{s}</span>;
}

function SourceBadge({ source }: { source: string }) {
  const s = source?.toLowerCase();
  if (s === "voice_agent") return <span className="badge badge-purple">ðŸŽ™ Voice</span>;
  if (s === "admin") return <span className="badge badge-neutral">Admin</span>;
  return <span className="badge badge-neutral">{s}</span>;
}

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    new_consultation: "New",
    follow_up: "Follow-up",
    review: "Review",
    emergency: "Emergency",
  };
  return <span className="badge badge-neutral">{map[type] || type}</span>;
}

// â”€â”€ Pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function DashboardPage({ clinic, stats }: { clinic: Clinic | null; stats: Stats | null }) {
  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: "#eff6ff" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div className="stat-label">Doctors</div>
          <div className="stat-value">{stats?.doctors ?? "â€”"}</div>
          <div className="stat-sub">Active medical staff</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: "#f0fdf4" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </div>
          <div className="stat-label">Total Appointments</div>
          <div className="stat-value">{stats?.appointments_total ?? "â€”"}</div>
          <div className="stat-sub">All time records</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: "#fffbeb" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div className="stat-label">Patients</div>
          <div className="stat-value">{stats?.patients ?? "â€”"}</div>
          <div className="stat-sub">Registered in system</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: "#f5f3ff" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <div className="stat-label">Slots Generated</div>
          <div className="stat-value">{stats?.slots_total ?? "â€”"}</div>
          <div className="stat-sub">Available time windows</div>
        </div>
      </div>

      {clinic && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title">Clinic Information</span>
          </div>
          <div className="card-body">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600, marginBottom: 4 }}>Clinic Name</div>
                <div style={{ fontWeight: 600, color: "var(--text)" }}>{clinic.name}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600, marginBottom: 4 }}>Address</div>
                <div style={{ color: "var(--text)" }}>{clinic.address || "â€”"}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600, marginBottom: 4 }}>Timezone</div>
                <div style={{ color: "var(--text)" }}>{clinic.timezone}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600, marginBottom: 4 }}>Clinic ID</div>
                <div className="tag">{clinic.id}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">System Status</span>
        </div>
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            {[
              { label: "FastAPI Backend", status: "Operational", color: "var(--success)", bg: "var(--success-light)" },
              { label: "PostgreSQL DB", status: "Connected", color: "var(--success)", bg: "var(--success-light)" },
              { label: "Voice Agent", status: "Configured", color: "var(--warning)", bg: "var(--warning-light)" },
            ].map(s => (
              <div key={s.label} style={{ padding: "12px 16px", background: s.bg, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>{s.label}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: s.color }}>{s.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function AppointmentsPage({ appointments, loading, onRefresh }: {
  appointments: Appointment[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [filter, setFilter] = useState("ALL");

  const filtered = filter === "ALL" ? appointments : appointments.filter(a => a.status?.toUpperCase() === filter);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div className="filter-bar" style={{ marginBottom: 0 }}>
          {["ALL", "BOOKED", "CANCELLED", "RESCHEDULED"].map(f => (
            <button key={f} className={`filter-btn ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
              {f === "ALL" ? `All (${appointments.length})` : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        <button
          onClick={onRefresh}
          style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border-strong)", background: "var(--bg-card)", cursor: "pointer", fontSize: 12, color: "var(--text-muted)" }}
        >
          {Icon.refresh} Refresh
        </button>
      </div>

      <div className="card">
        {loading ? (
          <div className="loading-wrap"><div className="spinner" /><span>Loading appointments...</span></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" strokeWidth="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <p>No appointments found</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Appointment</th>
                  <th>Slot Time</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Booked On</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(appt => (
                  <tr key={appt.id}>
                    <td>
                      <div className="td-primary">{appt.patient_name || "Unknown"}</div>
                      <div className="td-muted">{appt.patient_phone || "â€”"}</div>
                    </td>
                    <td>
                      <div className="td-primary">{appt.doctor_name || "â€”"}</div>
                      <div className="td-muted">{appt.department_name || "â€”"}</div>
                    </td>
                    <td>
                      <TypeBadge type={appt.appointment_type} />
                      {appt.reason && (
                        <div className="td-muted" style={{ marginTop: 4, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={appt.reason}>{appt.reason}</div>
                      )}
                    </td>
                    <td>
                      {appt.slot_start_time ? (
                        <>
                          <div className="td-primary" style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            {Icon.clock}
                            {fmtDateTime(appt.slot_start_time)}
                          </div>
                          {appt.slot_end_time && (
                            <div className="td-muted">until {new Date(appt.slot_end_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</div>
                          )}
                        </>
                      ) : <span style={{ color: "var(--text-light)" }}>â€”</span>}
                    </td>
                    <td><StatusBadge status={appt.status} /></td>
                    <td><SourceBadge source={appt.booking_source} /></td>
                    <td>
                      <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{fmtDate(appt.created_at)}</div>
                      {appt.rescheduled_from_appointment_id && (
                        <div style={{ fontSize: 11, color: "var(--warning)", marginTop: 2 }}>â†© Rescheduled</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function DoctorsPage({ doctors, loading }: { doctors: Doctor[]; loading: boolean }) {
  if (loading) {
    return <div className="loading-wrap"><div className="spinner" /><span>Loading doctors...</span></div>;
  }

  return (
    <div className="doctor-grid">
      {doctors.map(doc => (
        <div key={doc.id} className="doctor-card">
          <div className="doctor-avatar">{initials(doc.name)}</div>
          <div className="doctor-name">{doc.name}</div>
          {doc.qualification && <div className="doctor-dept">{doc.qualification}</div>}
          {doc.specialization && (
            <div style={{ marginTop: 8 }}>
              <span className="badge badge-purple" style={{ fontSize: 11 }}>{doc.specialization}</span>
            </div>
          )}
          {doc.consultation_fee != null && (
            <div className="doctor-meta">â‚¹{doc.consultation_fee} consultation fee</div>
          )}
          {doc.weekly_schedules && doc.weekly_schedules.length > 0 && (
            <div className="schedule-row">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              {doc.weekly_schedules.map(s => DAYS[s.day_of_week]).join(", ")}
              Â· {doc.weekly_schedules[0]?.start_time?.slice(0,5)} â€“ {doc.weekly_schedules[0]?.end_time?.slice(0,5)}
            </div>
          )}
          <div style={{ marginTop: 10 }}>
            <span className={`badge ${doc.active ? "badge-active" : "badge-neutral"}`}>{doc.active ? "Active" : "Inactive"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AgentGuidePage() {
  const steps = [
    {
      n: 1,
      title: "Start the Backend (FastAPI)",
      desc: "Open a PowerShell terminal and run:",
      code: `cd C:\\Projects\\clinicos-voice\\backend\n$env:PYTHONUTF8="1"\n.\\venv\\Scripts\\Activate\nuvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`,
      note: "Server is ready when you see: Uvicorn running on http://0.0.0.0:8000"
    },
    {
      n: 2,
      title: "Get Your Free API Keys",
      desc: "These are all the external services and where to get free keys:",
      table: [
        { service: "Groq (LLM)", link: "console.groq.com", free: "100% FREE Â· 14,400 req/day", card: false },
        { service: "Deepgram (STT)", link: "console.deepgram.com", free: "$200 free credit Â· No card needed", card: false },
        { service: "LiveKit Cloud", link: "cloud.livekit.io", free: "Free tier Â· Dev usage", card: false },
        { service: "ElevenLabs (TTS)", link: "elevenlabs.io", free: "10,000 chars/month free", card: false },
      ]
    },
    {
      n: 3,
      title: "Fill In Your .env File",
      desc: "Open backend/.env and set these values:",
      code: `GROQ_API_KEY=gsk_...your_key...\nDEEPGRAM_API_KEY=...your_key...\nELEVENLABS_API_KEY=...your_key...\nLIVEKIT_URL=wss://your-project.livekit.cloud\nLIVEKIT_API_KEY=API...\nLIVEKIT_API_SECRET=...your_secret...`,
    },
    {
      n: 4,
      title: "Start the Voice Agent",
      desc: "Open a second terminal:",
      code: `cd C:\\Projects\\clinicos-voice\\backend\n$env:PYTHONUTF8="1"\n.\\venv\\Scripts\\Activate\npython -m app.agents.livekit_agent dev`,
      note: "You should see: agent_ready logged to console"
    },
    {
      n: 5,
      title: "Test in the LiveKit Playground (FREE Â· No Phone Needed)",
      desc: "Open your browser and go to:",
      link: "https://agents-playground.livekit.io",
      note: "Enter your LiveKit URL, API Key, and Secret â†’ Click Connect â†’ Allow microphone â†’ Speak naturally."
    },
    {
      n: 6,
      title: "Example Things to Say",
      phrases: [
        "Hi, I'd like to book an appointment with Cardiology",
        "Can I reschedule my appointment? My number is 9876543210",
        "Please cancel my appointment",
        "I need to see a doctor urgently",
        "What slots are available with Dr. Sharma next week?",
      ]
    },
  ];

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <span className="card-title">Cost Summary â€” All Free for Development</span>
        </div>
        <div className="card-body">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
            {[
              { label: "Groq LLM", cost: "FREE", detail: "14,400 requests/day" },
              { label: "Deepgram STT", cost: "FREE*", detail: "$200 credit = ~100+ hrs" },
              { label: "LiveKit WebRTC", cost: "FREE", detail: "Developer tier" },
              { label: "ElevenLabs TTS", cost: "FREE*", detail: "10,000 chars/month" },
            ].map(c => (
              <div key={c.label} style={{ padding: "12px 14px", background: "var(--success-light)", border: "1px solid var(--success-border)", borderRadius: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>{c.label}</span>
                  <span style={{ fontWeight: 700, fontSize: 13, color: "var(--success)" }}>{c.cost}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>{c.detail}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--primary-light)", borderRadius: 8, fontSize: 12, color: "var(--primary)" }}>
            * Credit-based. Plenty for months of dev/testing. Production cost is ~â‚¹700â€“1,200/month for 500 calls.
          </div>
        </div>
      </div>

      {steps.map(step => (
        <div key={step.n} className="card" style={{ marginBottom: 14 }}>
          <div className="card-header">
            <span className="card-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--primary)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, flexShrink: 0 }}>{step.n}</span>
              {step.title}
            </span>
          </div>
          <div className="card-body" style={{ paddingTop: 14 }}>
            {step.desc && <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 10 }}>{step.desc}</p>}
            {step.code && (
              <pre style={{ background: "var(--bg-subtle)", border: "1px solid var(--border)", borderRadius: 8, padding: "12px 14px", fontSize: 12, fontFamily: "'SF Mono', 'Fira Code', monospace", color: "var(--text)", overflowX: "auto", whiteSpace: "pre-wrap" }}>{step.code}</pre>
            )}
            {step.table && (
              <table>
                <thead><tr><th>Service</th><th>Sign Up</th><th>Free Tier</th></tr></thead>
                <tbody>
                  {step.table.map(r => (
                    <tr key={r.service}>
                      <td className="td-primary">{r.service}</td>
                      <td><a href={`https://${r.link}`} target="_blank" rel="noopener" style={{ color: "var(--primary)", fontSize: 12 }}>{r.link}</a></td>
                      <td><span className="badge badge-active">{r.free}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {step.link && (
              <a href={step.link} target="_blank" rel="noopener"
                style={{ display: "inline-block", padding: "8px 16px", background: "var(--primary)", color: "white", borderRadius: 6, fontSize: 13, fontWeight: 600, textDecoration: "none", marginTop: 6 }}>
                â†’ {step.link}
              </a>
            )}
            {step.phrases && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {step.phrases.map((p, i) => (
                  <div key={i} style={{ padding: "8px 12px", background: "var(--bg-subtle)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 13, color: "var(--text)" }}>
                    ðŸŽ™ "{p}"
                  </div>
                ))}
              </div>
            )}
            {step.note && (
              <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--primary-light)", borderRadius: 6, fontSize: 12, color: "var(--primary)", borderLeft: "3px solid var(--primary)" }}>
                {step.note}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// â”€â”€ Main App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

type Page = "dashboard" | "appointments" | "doctors" | "agent";

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [clinic, setClinic] = useState<Clinic | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loadingAppts, setLoadingAppts] = useState(false);
  const [loadingDoctors, setLoadingDoctors] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    if (!CLINIC_ID) { setInitialLoading(false); return; }

    Promise.all([
      fetch(`${API}/api/v1/clinics/${CLINIC_ID}`).then(r => r.json()).catch(() => null),
      fetch(`${API}/api/v1/admin/stats?clinic_id=${CLINIC_ID}`, {
        headers: { "X-Admin-API-Key": ADMIN_KEY }
      }).then(r => r.json()).catch(() => null),
    ]).then(([c, s]) => {
      setClinic(c);
      setStats(s);
    }).finally(() => setInitialLoading(false));
  }, []);

  const loadAppointments = () => {
    if (!CLINIC_ID) return;
    setLoadingAppts(true);
    fetch(`${API}/api/v1/clinics/${CLINIC_ID}/appointments?limit=100`)
      .then(r => r.json())
      .then(data => setAppointments(Array.isArray(data) ? data : []))
      .catch(() => setAppointments([]))
      .finally(() => setLoadingAppts(false));
  };

  const loadDoctors = () => {
    if (!CLINIC_ID) return;
    setLoadingDoctors(true);
    fetch(`${API}/api/v1/clinics/${CLINIC_ID}/doctors`)
      .then(r => r.json())
      .then(data => setDoctors(Array.isArray(data) ? data : []))
      .catch(() => setDoctors([]))
      .finally(() => setLoadingDoctors(false));
  };

  useEffect(() => {
    if (page === "appointments" && appointments.length === 0) loadAppointments();
    if (page === "doctors" && doctors.length === 0) loadDoctors();
  }, [page]);

  const navItems: { id: Page; label: string; icon: JSX.Element }[] = [
    { id: "dashboard", label: "Overview", icon: Icon.dashboard },
    { id: "appointments", label: "Appointments", icon: Icon.appointments },
    { id: "doctors", label: "Doctors", icon: Icon.doctors },
    { id: "agent", label: "Test Voice Agent", icon: Icon.agent },
  ];

  const pageTitle: Record<Page, { title: string; sub: string }> = {
    dashboard: { title: "Overview", sub: clinic?.name || "ClinicOS Voice" },
    appointments: { title: "Appointments", sub: `${appointments.length} records` },
    doctors: { title: "Medical Staff", sub: `${doctors.length} doctors registered` },
    agent: { title: "Voice Agent Setup", sub: "Step-by-step guide to test the AI receptionist" },
  };

  if (initialLoading) {
    return (
      <div className="loading-wrap" style={{ minHeight: "100vh" }}>
        <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
        <span style={{ fontSize: 14, color: "var(--text-muted)" }}>Loading ClinicOS...</span>
      </div>
    );
  }

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>ClinicOS Voice</h1>
          <p>Admin Dashboard</p>
        </div>
        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
          {navItems.map(item => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => setPage(item.id)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="agent-status">
            <div className="agent-dot" />
            <span>Backend Online</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main">
        <div className="topbar">
          <div>
            <div className="topbar-title">{pageTitle[page].title}</div>
            <div className="topbar-sub">{pageTitle[page].sub}</div>
          </div>
        </div>
        <div className="content">
          {page === "dashboard" && <DashboardPage clinic={clinic} stats={stats} />}
          {page === "appointments" && (
            <AppointmentsPage
              appointments={appointments}
              loading={loadingAppts}
              onRefresh={loadAppointments}
            />
          )}
          {page === "doctors" && <DoctorsPage doctors={doctors} loading={loadingDoctors} />}
          {page === "agent" && <AgentGuidePage />}
        </div>
      </main>
    </div>
  );
}
