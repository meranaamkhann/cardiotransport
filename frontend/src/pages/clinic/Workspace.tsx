import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download } from "../../api/client";
import type { AssessmentRecord, AuditRow, CalibrationPreview, CalibrationRow, PatientDetail, PatientRow, StaffUser } from "../../api/types";
import AssessmentView from "../../components/AssessmentView";
import { TrendChart } from "../../components/charts";
import { Card, EmptyState, ErrorState, Field, LevelBadge, Notice, Skeleton, Spinner, Tabs, day, when } from "../../components/ui";

const LEVELS: { id: string; label: string }[] = [
  { id: "all", label: "All" }, { id: "emergency", label: "Emergency" }, { id: "urgent", label: "Same day" }, { id: "prompt", label: "Within days" }, { id: "soon", label: "Soon" }, { id: "routine", label: "Routine" },
];

export function ReviewQueue() {
  const [level, setLevel] = useState("all");
  const [q, setQ] = useState("");
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["queue"], queryFn: () => api<AssessmentRecord[]>("/clinic/queue"), refetchInterval: 30_000 });
  if (isLoading) return <div className="stack"><Skeleton lines={5} height={24} /></div>;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  const counts = data.reduce<Record<string, number>>((acc, a) => ({ ...acc, [a.urgency]: (acc[a.urgency] ?? 0) + 1 }), {});
  const shown = data.filter((a) => (level === "all" || a.urgency === level) && (!q.trim() || (a.patient_name ?? "").toLowerCase().includes(q.trim().toLowerCase())));
  return (
    <div className="stack">
      <div><h1>Review queue</h1><p className="muted">Unreviewed assessments from patients who share their records with your clinic, most urgent first.</p></div>
      {(counts.emergency ?? 0) > 0 && <Notice tone="danger" title={`${counts.emergency} emergency-level assessment${counts.emergency === 1 ? "" : "s"} waiting`}>Contact these patients first.</Notice>}
      <div className="row">
        <div className="filter-chips" role="group" aria-label="Filter by urgency">
          {LEVELS.map((l) => (
            <button key={l.id} className={level === l.id ? "on" : ""} aria-pressed={level === l.id} onClick={() => setLevel(l.id)}>
              {l.label}{l.id === "all" ? ` (${data.length})` : counts[l.id] ? ` (${counts[l.id]})` : ""}
            </button>
          ))}
        </div>
        <input aria-label="Search patients" className="search" placeholder="Search by patient name" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {data.length === 0 ? <EmptyState title="Queue is clear">New patient assessments will appear here.</EmptyState> : shown.length === 0 ? <EmptyState title="Nothing matches these filters" /> : (
        <div className="card scroll">
          <table className="plain wide">
            <thead><tr><th>Urgency</th><th>Patient</th><th>Assessment</th><th>Submitted</th></tr></thead>
            <tbody>
              {shown.map((a) => (
                <tr key={a.id}><td><LevelBadge level={a.urgency} /></td><td><Link to={`/clinic/patients/${a.patient_id}?assessment=${a.id}`}>{a.patient_name}</Link></td>
                  <td>{a.headline}</td><td>{when(a.created_at)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function PatientDirectory() {
  const [q, setQ] = useState("");
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["patients", q], queryFn: () => api<PatientRow[]>(`/clinic/patients?q=${encodeURIComponent(q)}`) });
  return (
    <div className="stack">
      <h1>Patients</h1>
      <Field id="search" label="Search by name"><input id="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Start typing a name" /></Field>
      {isLoading ? <Spinner /> : error || !data ? <ErrorState error={error} retry={() => void refetch()} /> : data.length === 0 ? (
        <EmptyState title="No patients found">Patients appear here once they join your clinic with code and consent to share.</EmptyState>
      ) : (
        <div className="card scroll">
          <table className="plain wide">
            <thead><tr><th>Name</th><th>Latest assessment</th><th>Urgency</th><th>Pending review</th></tr></thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}><td><Link to={`/clinic/patients/${p.id}`}>{p.name}</Link></td><td>{p.last_assessment ? `${p.last_assessment.headline} · ${day(p.last_assessment.created_at)}` : "None"}</td>
                  <td>{p.last_assessment ? <LevelBadge level={p.last_assessment.urgency} /> : "—"}</td><td>{p.pending_review}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

type Tab = "assessments" | "measurements" | "notes" | "appointments";

export function PatientPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("assessments");
  const [selected, setSelected] = useState<number | null>(() => Number(new URLSearchParams(window.location.search).get("assessment")) || null);
  const [kind, setKind] = useState("systolic");
  const [summary, setSummary] = useState("");
  const [note, setNote] = useState("");
  const [appt, setAppt] = useState({ when: "", reason: "" });
  const [error, setError] = useState("");
  const key = ["patient", id];
  const { data, error: loadError, isLoading, refetch } = useQuery({ queryKey: key, queryFn: () => api<PatientDetail>(`/clinic/patients/${id}`) });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: key }); void queryClient.invalidateQueries({ queryKey: ["queue"] }); };
  const review = useMutation({ mutationFn: (aid: number) => api(`/clinic/assessments/${aid}/review`, { method: "POST", body: { summary } }), onSuccess: () => { setSummary(""); refresh(); }, onError: (e) => setError(e instanceof Error ? e.message : "Failed") });
  const addNote = useMutation({ mutationFn: () => api(`/clinic/patients/${id}/notes`, { method: "POST", body: { body: note, assessment_id: selected } }), onSuccess: () => { setNote(""); refresh(); }, onError: (e) => setError(e instanceof Error ? e.message : "Failed") });
  const schedule = useMutation({ mutationFn: () => api(`/clinic/patients/${id}/appointments`, { method: "POST", body: { scheduled_at: new Date(appt.when).toISOString(), reason: appt.reason } }), onSuccess: () => { setAppt({ when: "", reason: "" }); refresh(); }, onError: (e) => setError(e instanceof Error ? e.message : "Failed") });
  const setStatus = useMutation({ mutationFn: ({ aid, status }: { aid: number; status: string }) => api(`/clinic/appointments/${aid}`, { method: "PATCH", body: { status } }), onSuccess: refresh });
  if (isLoading) return <Spinner />;
  if (loadError || !data) return <ErrorState error={loadError} retry={() => void refetch()} />;
  const current = data.assessments.find((a) => a.id === selected) ?? data.assessments[0] ?? null;
  const rows = data.measurements.filter((m) => m.kind === kind);
  return (
    <div className="stack">
      <Link to="/clinic/patients" className="no-print">← Patients</Link>
      <div className="row between"><div><h1>{data.patient.name}</h1><p className="muted">{data.patient.email}{data.profile.birth_year ? ` · born ${data.profile.birth_year}` : ""}{data.profile.sex ? ` · ${data.profile.sex}` : ""}</p></div>
        <div className="row"><button className="btn ghost small" onClick={() => void download(`/clinic/patients/${id}/export/assessments.csv`, `patient-${id}-assessments.csv`)}>Assessments CSV</button>
          <button className="btn ghost small" onClick={() => void download(`/clinic/patients/${id}/export/measurements.csv`, `patient-${id}-measurements.csv`)}>Measurements CSV</button></div></div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "assessments", label: "Assessments" }, { id: "measurements", label: "Measurements" }, { id: "notes", label: `Notes (${data.notes.length})` }, { id: "appointments", label: "Appointments" }]} />
      {error && <Notice tone="warn">{error}</Notice>}
      {tab === "assessments" && (data.assessments.length === 0 ? <EmptyState title="No assessments yet" /> : (
        <div className="split">
          <ul className="list pick">
            {data.assessments.map((a) => (
              <li key={a.id} className={current?.id === a.id ? "on" : ""}><button onClick={() => setSelected(a.id)}><strong>{a.headline}</strong><span className="muted small">{when(a.created_at)} · {a.status}</span></button><LevelBadge level={a.urgency} /></li>
            ))}
          </ul>
          {current && (
            <AssessmentView a={current}
              actions={<button className="btn ghost small" onClick={() => void download(`/clinic/assessments/${current.id}/report.pdf`, `cardiolens-assessment-${current.id}.pdf`)}>Download PDF report</button>}
              review={current.status === "submitted" ? (
                <form onSubmit={(e: FormEvent) => { e.preventDefault(); setError(""); review.mutate(current.id); }} className="no-print">
                  <Field id="summary" label="Your review"><textarea id="summary" rows={4} maxLength={3000} value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
                  <button className="btn primary" disabled={summary.trim().length < 3 || review.isPending}>Mark as reviewed</button>
                </form>
              ) : undefined} />
          )}
        </div>
      ))}
      {tab === "measurements" && (
        <Card>
          <select aria-label="Measurement" value={kind} onChange={(e) => setKind(e.target.value)}>{["systolic", "diastolic", "cholesterol", "glucose", "weight", "resting_hr"].map((k) => <option key={k} value={k}>{k.replace("_", " ")}</option>)}</select>
          {rows.length < 2 ? <EmptyState title="Not enough readings to chart" /> : <TrendChart rows={rows} unit={rows[0].unit} />}
        </Card>
      )}
      {tab === "notes" && (
        <Card>
          <form onSubmit={(e) => { e.preventDefault(); setError(""); addNote.mutate(); }}>
            <Field id="note" label="Add a clinical note" hint="Notes are encrypted at rest and visible to clinicians in this clinic."><textarea id="note" rows={3} maxLength={5000} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            <button className="btn primary" disabled={!note.trim() || addNote.isPending}>Save note</button>
          </form>
          {data.notes.length === 0 ? <EmptyState title="No notes yet" /> : <ul className="list">{data.notes.map((n) => <li key={n.id}><div><strong>{n.author}</strong><p>{n.body}</p><span className="muted small">{when(n.created_at)}{n.assessment_id ? ` · about assessment #${n.assessment_id}` : ""}</span></div></li>)}</ul>}
        </Card>
      )}
      {tab === "appointments" && (
        <Card>
          <form className="inline-form" onSubmit={(e) => { e.preventDefault(); setError(""); schedule.mutate(); }}>
            <Field id="aw" label="Date and time"><input id="aw" type="datetime-local" value={appt.when} onChange={(e) => setAppt({ ...appt, when: e.target.value })} /></Field>
            <Field id="ar" label="Reason"><input id="ar" value={appt.reason} onChange={(e) => setAppt({ ...appt, reason: e.target.value })} /></Field>
            <button className="btn primary" disabled={!appt.when || appt.reason.trim().length < 3}>Schedule</button>
          </form>
          {data.appointments.length === 0 ? <EmptyState title="No appointments" /> : (
            <ul className="list">
              {data.appointments.map((a) => (
                <li key={a.id}><div><strong>{a.reason}</strong><span className="muted small">{when(a.scheduled_at)}</span></div>
                  <div className="row"><span className="badge">{a.status}</span>
                    {a.status === "requested" && <button className="btn ghost small" onClick={() => setStatus.mutate({ aid: a.id, status: "confirmed" })}>Confirm</button>}
                    {a.status === "confirmed" && <button className="btn ghost small" onClick={() => setStatus.mutate({ aid: a.id, status: "completed" })}>Complete</button>}</div></li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

export function CalibrationPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CalibrationPreview | null>(null);
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["calibrations"], queryFn: () => api<CalibrationRow[]>("/clinic/calibration") });
  const run = useMutation({
    mutationFn: (apply: boolean) => { const form = new FormData(); form.append("file", file as File); form.append("apply", String(apply)); return api<CalibrationPreview>("/clinic/calibration", { method: "POST", form }); },
    onSuccess: (r) => { setPreview(r); void queryClient.invalidateQueries({ queryKey: ["calibrations"] }); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const off = useMutation({ mutationFn: (cid: number) => api(`/clinic/calibration/${cid}`, { method: "DELETE" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["calibrations"] }) });
  return (
    <div className="stack">
      <div><h1>Local calibration</h1>
        <p className="muted">A model trained elsewhere often over- or under-estimates risk in your population. Upload your own labelled angiography outcomes and CardioLens shifts its estimates to your local disease rate. Ranking quality does not change.</p></div>
      <Card title="Upload labelled cases">
        <ul>
          <li>At least 40 patients with a known angiography outcome, including 10 or more with and without disease.</li>
          <li>Columns: age, sex (1 male), cp (1 to 4), exang, trestbps, chol, fbs, optional restecg, thalach, oldpeak, and outcome (0 or 1).</li>
          <li>The file is processed in memory and never stored. Only the adjustment is saved.</li>
        </ul>
        <p><button className="linklike inline" onClick={() => void download("/clinic/calibration/template", "cardiolens_template.csv")}>Download the CSV template</button></p>
        <Field id="file" label="CSV file"><input id="file" type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); }} /></Field>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn ghost" disabled={!file || run.isPending} onClick={() => { setError(""); run.mutate(false); }}>Preview</button></div>
      </Card>
      {preview && (
        <Card title={`Preview from ${preview.n} patients (${preview.events} with disease)`}>
          {preview.results.map((t) => (
            <div key={t.tier} className="tier-result">
              <h4>{t.tier === "core" ? "Simple model" : "Detailed model"}: {t.method === "slope" ? "baseline and spread adjusted" : "baseline shifted"}</h4>
              <p>Observed rate {Math.round(t.observed_rate * 100)}% against an unadjusted model average of {Math.round(t.mean_predicted_before * 100)}%.</p>
              <p>Cross-validated Brier score: {t.brier_before} before, {t.brier_after} after.</p>
            </div>
          ))}
          {preview.applied ? <Notice tone="good">Applied. New assessments by patients of this clinic show a locally calibrated estimate.</Notice>
            : <div className="actions"><button className="btn primary" onClick={() => run.mutate(true)} disabled={run.isPending}>Apply to this clinic</button></div>}
        </Card>
      )}
      <Card title="Calibration history">
        {!list.data || list.data.length === 0 ? <EmptyState title="No calibration applied">Your clinic uses the unadjusted model.</EmptyState> : (
          <ul className="list">
            {list.data.map((c) => <li key={c.id}><div><strong>{c.tier === "core" ? "Simple" : "Detailed"} model · {c.n} patients</strong><span className="muted small">{when(c.created_at)} · Brier {c.brier_before} → {c.brier_after}</span></div>
              {c.is_active ? <button className="btn ghost small" onClick={() => off.mutate(c.id)}>Deactivate</button> : <span className="badge">inactive</span>}</li>)}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function TeamPage() {
  const queryClient = useQueryClient();
  const [f, setF] = useState({ full_name: "", email: "", password: "", role: "clinician" });
  const [error, setError] = useState("");
  const users = useQuery({ queryKey: ["staff"], queryFn: () => api<StaffUser[]>("/admin/users") });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api<AuditRow[]>("/admin/audit") });
  const create = useMutation({ mutationFn: () => api("/admin/users", { method: "POST", body: f }), onSuccess: () => { setF({ full_name: "", email: "", password: "", role: "clinician" }); void queryClient.invalidateQueries({ queryKey: ["staff"] }); }, onError: (e) => setError(e instanceof Error ? e.message : "Failed") });
  const toggle = useMutation({ mutationFn: (u: StaffUser) => api(`/admin/users/${u.id}/active?active=${!u.is_active}`, { method: "PATCH" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["staff", "audit"] }) });
  return (
    <div className="stack">
      <h1>Team and audit</h1>
      <Card title="Add a team member">
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); setError(""); create.mutate(); }}>
          <Field id="n" label="Full name"><input id="n" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
          <Field id="e" label="Email"><input id="e" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field id="p" label="Temporary password"><input id="p" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <Field id="r" label="Role"><select id="r" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}><option value="clinician">Clinician</option><option value="researcher">Researcher</option><option value="clinic_admin">Clinic administrator</option></select></Field>
          <button className="btn primary" disabled={create.isPending}>Add</button>
        </form>
        {error && <Notice tone="warn">{error}</Notice>}
      </Card>
      <Card title="Team">
        {users.isLoading ? <Spinner /> : users.error ? <ErrorState error={users.error} /> : (
          <ul className="list">{users.data?.map((u) => <li key={u.id}><div><strong>{u.full_name}</strong><span className="muted small">{u.email} · {u.role.replace("_", " ")}</span></div>
            <button className="btn ghost small" onClick={() => toggle.mutate(u)}>{u.is_active ? "Deactivate" : "Reactivate"}</button></li>)}</ul>
        )}
      </Card>
      <Card title="Audit log">
        {audit.isLoading ? <Spinner /> : audit.error ? <ErrorState error={audit.error} /> : (
          <div className="scroll"><table className="plain wide"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th></tr></thead>
            <tbody>{audit.data?.map((e) => <tr key={e.id}><td>{when(e.created_at)}</td><td>{e.actor}</td><td>{e.action.replace(/_/g, " ")}</td><td>{e.entity}{e.entity_id ? ` #${e.entity_id}` : ""}</td></tr>)}</tbody></table></div>
        )}
      </Card>
    </div>
  );
}
