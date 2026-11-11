import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download } from "../../api/client";
import type { AppointmentRecord, AssessmentRecord, Measurement, Profile, User } from "../../api/types";
import AssessmentView from "../../components/AssessmentView";
import { TrendChart } from "../../components/charts";
import { bloodPressure, cholesterol as cholStatus, glucose as gluStatus } from "../../components/status";
import { useToast } from "../../components/Toast";
import { Card, Choices, EmptyState, ErrorState, Field, LevelBadge, Notice, Spinner, StatusChip, Tabs, when } from "../../components/ui";
import type { AccessLogRow } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";

export function Assessments() {
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["assessments"], queryFn: () => api<AssessmentRecord[]>("/me/assessments") });
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  return (
    <div className="stack">
      <div className="row between"><h1>Assessment history</h1>
        <button className="btn ghost small" onClick={() => void download("/me/export/assessments.csv", "assessments.csv")}>Export CSV</button></div>
      {data.length === 0 ? <EmptyState title="No assessments yet" action={<Link className="btn primary" to="/app/symptoms">Start a symptom assessment</Link>}>Your completed assessments will appear here.</EmptyState> : (
        <div className="card scroll">
          <table className="plain wide">
            <thead><tr><th>Date</th><th>Type</th><th>Result</th><th>Urgency</th><th>Review</th></tr></thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id}><td>{when(a.created_at)}</td><td>{a.kind}</td><td><Link to={`/app/assessments/${a.id}`}>{a.headline}</Link></td>
                  <td><LevelBadge level={a.urgency} /></td><td>{a.status === "reviewed" ? `By ${a.reviewer}` : "Pending"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function AssessmentDetail() {
  const { id } = useParams();
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["assessment", id], queryFn: () => api<AssessmentRecord>(`/me/assessments/${id}`) });
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;
  return (
    <div className="stack">
      <Link to="/app/assessments" className="no-print">← All assessments</Link>
      <AssessmentView a={data} actions={<><button className="btn primary small" onClick={() => void download(`/me/assessments/${data.id}/report.pdf`, `cardiolens-assessment-${data.id}.pdf`)}>Download PDF report</button>
        <button className="btn ghost small" onClick={() => window.print()}>Print</button></>} />
    </div>
  );
}

const KINDS = [
  { id: "systolic", label: "Systolic BP" }, { id: "diastolic", label: "Diastolic BP" }, { id: "cholesterol", label: "Cholesterol" },
  { id: "glucose", label: "Glucose" }, { id: "weight", label: "Weight" }, { id: "resting_hr", label: "Resting heart rate" },
] as const;

export function Measurements() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<Measurement["kind"]>("systolic");
  const [value, setValue] = useState("");
  const [at, setAt] = useState("");
  const [error, setError] = useState("");
  const { data, error: loadError, isLoading, refetch } = useQuery({ queryKey: ["measurements"], queryFn: () => api<Measurement[]>("/me/measurements") });
  const add = useMutation({
    mutationFn: () => api("/me/measurements", { method: "POST", body: { kind, value: Number(value), measured_at: at ? new Date(at).toISOString() : null } }),
    onSuccess: () => { setValue(""); setAt(""); toast.success("Reading saved."); void queryClient.invalidateQueries({ queryKey: ["measurements"] }); void queryClient.invalidateQueries({ queryKey: ["dashboard"] }); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not save."),
  });
  const remove = useMutation({ mutationFn: (id: number) => api(`/me/measurements/${id}`, { method: "DELETE" }), onSuccess: () => { toast.success("Reading deleted."); void queryClient.invalidateQueries({ queryKey: ["measurements"] }); } });
  if (isLoading) return <Spinner />;
  if (loadError || !data) return <ErrorState error={loadError} retry={() => void refetch()} />;
  const rows = data.filter((m) => m.kind === kind);
  const latest = (k: Measurement["kind"]) => data.find((m) => m.kind === k)?.value;
  const bp = bloodPressure(latest("systolic"), latest("diastolic"));
  const chol = cholStatus(latest("cholesterol"));
  const glu = gluStatus(latest("glucose"));
  const submit = (e: FormEvent) => { e.preventDefault(); setError(""); if (!value) return setError("Enter a value."); add.mutate(); };
  return (
    <div className="stack">
      <div className="row between"><h1>Measurements</h1><button className="btn ghost small" onClick={() => void download("/me/export/measurements.csv", "measurements.csv")}>Export CSV</button></div>
      <Card title="Add a reading">
        <form onSubmit={submit} className="inline-form">
          <Field id="kind" label="Measurement"><select id="kind" value={kind} onChange={(e) => setKind(e.target.value as Measurement["kind"])}>{KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></Field>
          <Field id="value" label="Value"><input id="value" type="number" step="any" value={value} onChange={(e) => setValue(e.target.value)} /></Field>
          <Field id="at" label="When (optional)"><input id="at" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} /></Field>
          <button className="btn primary" disabled={add.isPending}>Save</button>
        </form>
        {error && <Notice tone="warn">{error}</Notice>}
      </Card>
      <div className="stats three">
        <div className="stat"><span className="stat-label">Blood pressure</span><span className="stat-value">{latest("systolic") ? `${latest("systolic")}/${latest("diastolic") ?? "?"}` : "—"}</span><StatusChip tone={bp.tone} label={bp.label} /></div>
        <div className="stat"><span className="stat-label">Cholesterol</span><span className="stat-value">{latest("cholesterol") ?? "—"}</span><StatusChip tone={chol.tone} label={chol.label} /></div>
        <div className="stat"><span className="stat-label">Fasting glucose</span><span className="stat-value">{latest("glucose") ?? "—"}</span><StatusChip tone={glu.tone} label={glu.label} /></div>
      </div>
      <p className="muted small">Labels use published guideline cut-offs and are not a diagnosis. One reading is never enough to diagnose anything.</p>
      <Tabs tabs={KINDS.map((k) => ({ id: k.id, label: k.label }))} value={kind} onChange={setKind} />
      <Card title={`${KINDS.find((k) => k.id === kind)?.label} over time`}>
        {rows.length < 2 ? <EmptyState title={rows.length === 0 ? "No readings yet" : "Add one more reading to see a trend"}>Readings you add or save from assessments appear here.</EmptyState> : <TrendChart rows={rows} unit={rows[0].unit} />}
        {rows.length > 0 && (
          <div className="scroll"><table className="plain"><tbody>
            {rows.slice(0, 12).map((m) => <tr key={m.id}><td>{when(m.measured_at)}</td><td>{m.value} {m.unit}</td>
              <td><button className="btn ghost small" aria-label={`Delete reading from ${when(m.measured_at)}`} onClick={() => remove.mutate(m.id)}>Delete</button></td></tr>)}
          </tbody></table></div>
        )}
      </Card>
    </div>
  );
}

export function Appointments() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const [when_, setWhen] = useState("");
  const [reason, setReason] = useState("");
  const [clinician, setClinician] = useState("");
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["appointments"], queryFn: () => api<AppointmentRecord[]>("/me/appointments") });
  const clinicians = useQuery({ queryKey: ["clinicians"], queryFn: () => api<{ id: number; name: string }[]>("/me/clinicians"), enabled: Boolean(user?.clinic) });
  const create = useMutation({
    mutationFn: () => api("/me/appointments", { method: "POST", body: { scheduled_at: new Date(when_).toISOString(), reason, clinician_id: clinician ? Number(clinician) : null } }),
    onSuccess: () => { setReason(""); setWhen(""); toast.success("Appointment requested."); void queryClient.invalidateQueries({ queryKey: ["appointments"] }); void queryClient.invalidateQueries({ queryKey: ["dashboard"] }); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not request."),
  });
  const cancel = useMutation({ mutationFn: (id: number) => api(`/me/appointments/${id}`, { method: "PATCH", body: { status: "cancelled" } }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["appointments"] }) });
  if (list.isLoading) return <Spinner />;
  if (list.error || !list.data) return <ErrorState error={list.error} />;
  return (
    <div className="stack">
      <h1>Appointments</h1>
      {!user?.clinic ? <Notice tone="info" title="Join a clinic to request appointments">Add a clinic code in <Link to="/app/profile">Profile and privacy</Link>.</Notice> : (
        <Card title="Request an appointment">
          <form className="inline-form" onSubmit={(e) => { e.preventDefault(); setError(""); if (!when_ || reason.trim().length < 3) return setError("Choose a time and give a short reason."); create.mutate(); }}>
            <Field id="when" label="Preferred time"><input id="when" type="datetime-local" value={when_} onChange={(e) => setWhen(e.target.value)} /></Field>
            <Field id="reason" label="Reason"><input id="reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} /></Field>
            <Field id="clin" label="Clinician (optional)"><select id="clin" value={clinician} onChange={(e) => setClinician(e.target.value)}><option value="">Any</option>{clinicians.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
            <button className="btn primary" disabled={create.isPending}>Request</button>
          </form>
          {error && <Notice tone="warn">{error}</Notice>}
        </Card>
      )}
      <Card title="Your appointments">
        {list.data.length === 0 ? <EmptyState title="No appointments">Requested and confirmed appointments appear here.</EmptyState> : (
          <ul className="list">
            {list.data.map((a) => (
              <li key={a.id}><div><strong>{a.reason}</strong><span className="muted small">{when(a.scheduled_at)}{a.clinician ? ` · ${a.clinician}` : ""}</span></div>
                <div className="row"><span className="badge">{a.status}</span>
                  {(a.status === "requested" || a.status === "confirmed") && <button className="btn ghost small" onClick={() => cancel.mutate(a.id)}>Cancel</button>}</div></li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function ProfilePage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { user, refresh, signOut } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState("");
  const log = useQuery({ queryKey: ["access-log"], queryFn: () => api<AccessLogRow[]>("/me/access-log") });
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const { data, isLoading, error: loadError } = useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/me/profile") });
  const [f, setF] = useState<Profile | null>(null);
  const form = f ?? data ?? null;
  const save = useMutation({
    mutationFn: (p: Profile) => api("/me/profile", { method: "PUT", body: p }),
    onSuccess: () => { toast.success("Profile saved."); void queryClient.invalidateQueries(); void refresh(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not save."),
  });
  const join = useMutation({ mutationFn: () => api<User>("/auth/join-clinic", { method: "POST", body: { code } }), onSuccess: () => { setCode(""); void refresh(); toast.success("You joined the clinic."); }, onError: (e) => setError(e instanceof Error ? e.message : "Could not join.") });
  const leave = useMutation({ mutationFn: () => api<User>("/auth/leave-clinic", { method: "POST" }), onSuccess: () => { void refresh(); void queryClient.invalidateQueries({ queryKey: ["access-log"] }); toast.success("You left the clinic. It can no longer see your records."); } });
  const erase = useMutation({
    mutationFn: () => api("/me/delete-account", { method: "POST", body: { password: confirm } }),
    onSuccess: () => { toast.success("Your account and data were deleted."); signOut(); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not delete."),
  });
  if (isLoading || !form) return <Spinner />;
  if (loadError) return <ErrorState error={loadError} />;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setF({ ...form, [k]: v });
  return (
    <div className="stack">
      <h1>Profile and privacy</h1>
      <Card title="About you">
        <div className="grid2">
          <Field id="sex" label="Sex at birth"><Choices name="Sex" value={form.sex ?? ""} onChange={(v) => set("sex", v)} options={[{ value: "female", title: "Female" }, { value: "male", title: "Male" }]} /></Field>
          <Field id="by" label="Birth year"><input id="by" type="number" value={form.birth_year ?? ""} onChange={(e) => set("birth_year", e.target.value ? Number(e.target.value) : null)} /></Field>
          <Field id="ht" label="Height (cm)"><input id="ht" type="number" value={form.height_cm ?? ""} onChange={(e) => set("height_cm", e.target.value ? Number(e.target.value) : null)} /></Field>
          <Field id="act" label="Brisk activity (minutes per week)"><input id="act" type="number" value={form.activity_minutes ?? ""} onChange={(e) => set("activity_minutes", e.target.value ? Number(e.target.value) : null)} /></Field>
        </div>
        <Field id="smoke" label="Smoking"><Choices name="Smoking" value={form.smoking ?? ""} onChange={(v) => set("smoking", v)} options={[{ value: "never", title: "Never" }, { value: "former", title: "Former" }, { value: "current", title: "Current" }]} /></Field>
        <div className="checks">
          <label className="check"><input type="checkbox" checked={form.diabetes} onChange={(e) => set("diabetes", e.target.checked)} /><span>I have diabetes</span></label>
          <label className="check"><input type="checkbox" checked={form.family_history} onChange={(e) => set("family_history", e.target.checked)} /><span>A parent or sibling had early heart disease</span></label>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        {message && <Notice tone="good">{message}</Notice>}
        <div className="actions"><button className="btn primary" disabled={save.isPending} onClick={() => { setError(""); setMessage(""); save.mutate(form); }}>Save profile</button></div>
      </Card>
      <Card title="Clinic sharing">
        {user?.clinic ? (
          <>
            <p>Your records are visible to clinicians at <strong>{user.clinic.name}</strong>. Their access is recorded in an audit log.</p>
            <button className="btn ghost" onClick={() => leave.mutate()}>Stop sharing and leave clinic</button>
          </>
        ) : (
          <>
            <p>Your records are private. Enter a clinic code only if you want that clinic to see your assessments, measurements and appointments. You can leave at any time.</p>
            <div className="inline-form"><Field id="code" label="Clinic code"><input id="code" value={code} maxLength={16} onChange={(e) => setCode(e.target.value)} /></Field>
              <button className="btn primary" disabled={!code || join.isPending} onClick={() => { setError(""); join.mutate(); }}>Share with clinic</button></div>
          </>
        )}
      </Card>
      <Card title="Who has looked at your records">
        {log.isLoading ? <Spinner /> : !log.data || log.data.length === 0 ? <EmptyState title="Nobody yet">Whenever a clinician opens your record, it is listed here.</EmptyState> : (
          <ul className="list">{log.data.map((e) => <li key={e.id}><div><strong>{e.who}</strong><span className="muted small">{e.action}</span></div><span className="muted small">{when(e.when)}</span></li>)}</ul>
        )}
      </Card>
      <Card title="Your data">
        <p>Download everything CardioLens holds about you, or delete your account and all of it permanently.</p>
        <div className="actions"><button className="btn ghost" onClick={() => void download("/me/export.json", "cardiolens-my-data.json")}>Download my data (JSON)</button>
          <button className="btn ghost danger-text" onClick={() => setDeleting(!deleting)}>Delete my account</button></div>
        {deleting && (
          <div className="danger-zone">
            <p>This removes your profile, assessments, measurements and appointments, and clinicians&apos; notes about you. It cannot be undone.</p>
            <Field id="confirm" label="Enter your password to confirm"><input id="confirm" type="password" autoComplete="current-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
            <button className="btn danger" disabled={!confirm || erase.isPending} onClick={() => { setError(""); erase.mutate(); }}>Delete permanently</button>
          </div>
        )}
      </Card>
    </div>
  );
}
