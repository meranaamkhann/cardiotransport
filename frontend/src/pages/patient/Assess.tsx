import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { AssessmentRecord, Dashboard } from "../../api/types";
import { useToast } from "../../components/Toast";
import { Card, Choices, ErrorState, Field, Notice, NumberInput, Skeleton, Spinner } from "../../components/ui";

const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

const FLAGS = [
  { key: "pain_at_rest", text: "Chest pain or pressure that started at rest and has lasted more than 15 minutes" },
  { key: "pain_spreading", text: "Pain spreading to the arm, shoulder, jaw or back, with sweating or nausea" },
  { key: "fainting", text: "Fainting or nearly fainting" },
  { key: "sudden_breathlessness", text: "Sudden, severe shortness of breath" },
];

const HISTORY = [
  { key: "hypertension", text: "High blood pressure" }, { key: "diabetes", text: "Diabetes" }, { key: "high_cholesterol", text: "High cholesterol" },
  { key: "previous_heart_disease", text: "Known heart disease" }, { key: "family_history", text: "Close relative with early heart disease" },
];

function ProfileGate() {
  return (
    <Notice tone="info" title="Complete your profile first">
      We need your sex and birth year to run an assessment. <Link to="/app/profile">Open your profile</Link>.
    </Notice>
  );
}

const DRAFT = "cardiolens.symptom.draft";

const blank = {
  emergency: [] as string[], conditions: [] as string[], chest: "", effort: "" as "" | "yes" | "no", breath: "none", palpitations: false, dizziness: false,
  fatigue: false, duration: "", severity: "5", systolic: "", cholesterol: "", glucose: "", hasReports: false, ecg: "", maxHr: "", st: "",
};

type Form = typeof blank;

function loadDraft(): { form: Form; step: number } {
  try {
    const raw = window.sessionStorage.getItem(DRAFT);
    if (raw) {
      const parsed = JSON.parse(raw) as { form: Form; step: number };
      return { form: { ...blank, ...parsed.form }, step: Math.min(Math.max(parsed.step, 0), 4) };
    }
  } catch {
    return { form: blank, step: 0 };
  }
  return { form: blank, step: 0 };
}

const STEPS = ["Warning signs", "Symptoms", "History", "Numbers", "Review"];
const CHEST_TEXT: Record<string, string> = { none: "No chest discomfort", typical: "Pressure or tightness with effort", atypical: "Some of those features", non_anginal: "Pain that does not fit" };
const BREATH_TEXT: Record<string, string> = { none: "None", on_exertion: "On exertion", at_rest: "At rest" };

export function SymptomAssessment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const me = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/me/dashboard") });
  const initial = useState(loadDraft)[0];
  const [f, setF] = useState<Form>(initial.form);
  const [step, setStep] = useState(initial.step);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      window.sessionStorage.setItem(DRAFT, JSON.stringify({ form: f, step }));
    } catch {
      return;
    }
  }, [f, step]);

  const toggle = (key: "emergency" | "conditions", value: string) =>
    setF((s) => ({ ...s, [key]: s[key].includes(value) ? s[key].filter((v) => v !== value) : [...s[key], value] }));

  const submit = useMutation({
    mutationFn: () => api<AssessmentRecord>("/me/assessments/symptom", { method: "POST", body: {
      chest_discomfort: f.chest, discomfort_with_effort: f.effort === "yes", breathlessness: f.breath, palpitations: f.palpitations,
      dizziness: f.dizziness, fatigue: f.fatigue, duration: f.duration, severity: Number(f.severity), emergency: f.emergency, conditions: f.conditions,
      systolic: num(f.systolic), cholesterol: num(f.cholesterol), fasting_glucose: num(f.glucose),
      ecg: f.hasReports && f.ecg ? f.ecg : null, max_hr: f.hasReports ? num(f.maxHr) : null, st_depression: f.hasReports ? num(f.st) : null,
    } }),
    onSuccess: (a) => {
      try { window.sessionStorage.removeItem(DRAFT); } catch { /* storage unavailable */ }
      void queryClient.invalidateQueries();
      toast.success("Assessment saved.");
      navigate(`/app/assessments/${a.id}`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Something went wrong."),
  });

  if (me.isLoading) return <div className="stack"><Skeleton lines={4} height={22} /></div>;
  if (me.error) return <ErrorState error={me.error} />;
  if (!me.data?.user.profile_complete) return <ProfileGate />;

  const problem = (): string => {
    if (step === 1) {
      if (!f.chest) return "Choose the chest discomfort option that fits best.";
      if (f.chest !== "none" && !f.effort) return "Tell us whether effort brings the discomfort on.";
      if (!f.duration) return "Tell us how long you have had these symptoms.";
    }
    if (step === 3) {
      const ranges: [string, string, number, number][] = [["Blood pressure", f.systolic, 70, 260], ["Cholesterol", f.cholesterol, 80, 700], ["Fasting blood sugar", f.glucose, 40, 700]];
      for (const [name, raw, low, high] of ranges) {
        const v = num(raw);
        if (v !== null && (v < low || v > high)) return `${name} should be between ${low} and ${high}, or left blank.`;
      }
    }
    return "";
  };

  const next = () => {
    const issue = problem();
    setError(issue);
    if (!issue) setStep(step + 1);
  };

  return (
    <div className="stack">
      <div><h1>Symptom assessment</h1><p className="muted">Rules decide how urgent this is first. A research model adds a second opinion and can only raise the urgency. Your answers are kept only in this tab until you submit.</p></div>
      <ol className="stepper" aria-label="Progress">
        {STEPS.map((name, i) => (
          <li key={name} className={i === step ? "current" : i < step ? "done" : ""} aria-current={i === step ? "step" : undefined}>
            <button disabled={i > step} onClick={() => { setError(""); setStep(i); }}><span>{i < step ? "✓" : i + 1}</span>{name}</button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <Card title="Are you having any of these right now?">
          <div className="checks">
            {FLAGS.map((w) => (
              <label key={w.key} className="check"><input type="checkbox" checked={f.emergency.includes(w.key)} onChange={() => toggle("emergency", w.key)} /><span>{w.text}</span></label>
            ))}
          </div>
          {f.emergency.length > 0 && (
            <Notice tone="danger" title="Get emergency help now">
              These can be signs of a heart attack. Call your local emergency number (112 in India) and do not drive yourself. You can record this assessment afterwards.
              <div className="actions"><a className="btn danger" href="tel:112">Call 112</a></div>
            </Notice>
          )}
        </Card>
      )}

      {step === 1 && (
        <Card title="Your symptoms">
          <Field id="chest" label="Chest discomfort">
            <Choices name="Chest discomfort" value={f.chest} onChange={(v) => setF({ ...f, chest: v })} options={[
              { value: "none", title: "No chest discomfort" },
              { value: "typical", title: "Pressure or tightness with effort", text: "Squeezing or heaviness that comes with effort or stress and eases within minutes of rest." },
              { value: "atypical", title: "Some of those features", text: "Part of that pattern, for example lasting longer or coming at odd times." },
              { value: "non_anginal", title: "Pain that does not fit", text: "Sharp or pinpoint, changes with breathing or posture, or clearly muscular." }]} />
          </Field>
          {f.chest !== "" && f.chest !== "none" && (
            <Field id="effort" label="Does effort, such as stairs or a brisk walk, bring it on?">
              <Choices name="Effort" value={f.effort} onChange={(v) => setF({ ...f, effort: v })} options={[{ value: "yes", title: "Yes" }, { value: "no", title: "No" }]} />
            </Field>
          )}
          <Field id="breath" label="Breathlessness">
            <Choices name="Breathlessness" value={f.breath} onChange={(v) => setF({ ...f, breath: v })} options={[
              { value: "none", title: "None" }, { value: "on_exertion", title: "On exertion" }, { value: "at_rest", title: "At rest" }]} />
          </Field>
          <div className="checks">
            <label className="check"><input type="checkbox" checked={f.palpitations} onChange={(e) => setF({ ...f, palpitations: e.target.checked })} /><span>Palpitations (racing or irregular heartbeat)</span></label>
            <label className="check"><input type="checkbox" checked={f.dizziness} onChange={(e) => setF({ ...f, dizziness: e.target.checked })} /><span>Dizziness or light-headedness</span></label>
            <label className="check"><input type="checkbox" checked={f.fatigue} onChange={(e) => setF({ ...f, fatigue: e.target.checked })} /><span>Unusual tiredness</span></label>
          </div>
          <div className="grid2">
            <Field id="duration" label="How long have you had them?">
              <select id="duration" value={f.duration} onChange={(e) => setF({ ...f, duration: e.target.value })}>
                <option value="">Select</option><option value="minutes">Minutes</option><option value="hours">Hours</option><option value="days">Days</option><option value="weeks">Weeks</option><option value="months">Months or longer</option>
              </select>
            </Field>
            <Field id="severity" label={`Severity: ${f.severity} out of 10`}>
              <input id="severity" type="range" min={1} max={10} value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })} />
            </Field>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card title="Medical history">
          <div className="checks">
            {HISTORY.map((h) => <label key={h.key} className="check"><input type="checkbox" checked={f.conditions.includes(h.key)} onChange={() => toggle("conditions", h.key)} /><span>{h.text}</span></label>)}
          </div>
          <p className="hint">Skip this if none apply.</p>
        </Card>
      )}

      {step === 3 && (
        <Card title="Recent numbers (optional)">
          <p className="hint">Leave blank to use your latest saved measurements. Unknown values lower the model&apos;s confidence.</p>
          <div className="grid2">
            <Field id="sys" label="Blood pressure, top number"><NumberInput id="sys" value={f.systolic} onChange={(v) => setF({ ...f, systolic: v })} unit="mmHg" /></Field>
            <Field id="chol" label="Total cholesterol"><NumberInput id="chol" value={f.cholesterol} onChange={(v) => setF({ ...f, cholesterol: v })} unit="mg/dL" /></Field>
            <Field id="glu" label="Fasting blood sugar"><NumberInput id="glu" value={f.glucose} onChange={(v) => setF({ ...f, glucose: v })} unit="mg/dL" /></Field>
          </div>
          <label className="check"><input type="checkbox" checked={f.hasReports} onChange={(e) => setF({ ...f, hasReports: e.target.checked })} /><span>I have an ECG and stress-test report</span></label>
          {f.hasReports && (
            <div className="grid2">
              <Field id="ecg" label="Resting ECG"><select id="ecg" value={f.ecg} onChange={(e) => setF({ ...f, ecg: e.target.value })}><option value="">Select</option><option value="normal">Normal</option><option value="st_t_abnormality">ST-T wave abnormality</option><option value="lv_hypertrophy">Left ventricular hypertrophy</option></select></Field>
              <Field id="maxhr" label="Peak heart rate in the stress test"><NumberInput id="maxhr" value={f.maxHr} onChange={(v) => setF({ ...f, maxHr: v })} unit="bpm" /></Field>
              <Field id="st" label="ST depression"><NumberInput id="st" value={f.st} onChange={(v) => setF({ ...f, st: v })} unit="mm" step={0.1} /></Field>
            </div>
          )}
        </Card>
      )}

      {step === 4 && (
        <Card title="Check your answers">
          <table className="plain"><tbody>
            <tr><th>Warning signs</th><td>{f.emergency.length ? f.emergency.map((x) => x.replace(/_/g, " ")).join(", ") : "None"}</td><td><button className="linklike inline" onClick={() => setStep(0)}>Edit</button></td></tr>
            <tr><th>Chest discomfort</th><td>{CHEST_TEXT[f.chest]}{f.chest !== "none" ? (f.effort === "yes" ? ", brought on by effort" : ", not brought on by effort") : ""}</td><td><button className="linklike inline" onClick={() => setStep(1)}>Edit</button></td></tr>
            <tr><th>Breathlessness</th><td>{BREATH_TEXT[f.breath]}</td><td /></tr>
            <tr><th>Other symptoms</th><td>{[f.palpitations && "palpitations", f.dizziness && "dizziness", f.fatigue && "tiredness"].filter(Boolean).join(", ") || "None"}</td><td /></tr>
            <tr><th>Duration and severity</th><td>{f.duration}, {f.severity} out of 10</td><td /></tr>
            <tr><th>History</th><td>{f.conditions.length ? f.conditions.map((x) => x.replace(/_/g, " ")).join(", ") : "None"}</td><td><button className="linklike inline" onClick={() => setStep(2)}>Edit</button></td></tr>
            <tr><th>Numbers</th><td>{[f.systolic && `BP ${f.systolic}`, f.cholesterol && `cholesterol ${f.cholesterol}`, f.glucose && `glucose ${f.glucose}`].filter(Boolean).join(", ") || "From your saved measurements"}</td><td><button className="linklike inline" onClick={() => setStep(3)}>Edit</button></td></tr>
          </tbody></table>
        </Card>
      )}

      {error && <Notice tone="warn">{error}</Notice>}
      <div className="actions between">
        <button className="btn ghost" disabled={step === 0} onClick={() => { setError(""); setStep(step - 1); }}>Back</button>
        {step < 4
          ? <button className="btn primary" onClick={next}>Continue</button>
          : <button className="btn primary" onClick={() => { setError(""); submit.mutate(); }} disabled={submit.isPending}>{submit.isPending ? "Assessing…" : "Get my assessment"}</button>}
      </div>
    </div>
  );
}

export function WellnessAssessment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const me = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/me/dashboard") });
  const [f, setF] = useState({ systolic: "", diastolic: "", cholesterol: "", glucose: "", weight: "", activity: "", save: true, southAsian: true });
  const [error, setError] = useState("");
  const submit = useMutation({
    mutationFn: () => api<AssessmentRecord>("/me/assessments/wellness", { method: "POST", body: {
      systolic: num(f.systolic), diastolic: num(f.diastolic), cholesterol: num(f.cholesterol), fasting_glucose: num(f.glucose),
      weight_kg: num(f.weight), activity_minutes: num(f.activity), save_measurements: f.save, south_asian_cutoffs: f.southAsian } }),
    onSuccess: (a) => { void queryClient.invalidateQueries(); toast.success("Assessment saved."); navigate(`/app/assessments/${a.id}`); },
    onError: (e) => setError(e instanceof Error ? e.message : "Something went wrong."),
  });
  if (me.isLoading) return <Spinner />;
  if (me.error) return <ErrorState error={me.error} />;
  if (!me.data?.user.profile_complete) return <ProfileGate />;
  const latest = me.data.latest_measurements;
  return (
    <div className="stack">
      <div><h1>Wellness assessment</h1><p className="muted">Compares your numbers with published guideline cut-offs. It is a risk-factor review, not a prediction or a diagnosis.</p></div>
      <Card>
        <p className="hint">Blank fields use your latest saved measurement where you have one.</p>
        <div className="grid2">
          <Field id="w-sys" label="Blood pressure, top number" hint={latest.systolic ? `Latest saved: ${latest.systolic}` : undefined}><NumberInput id="w-sys" value={f.systolic} onChange={(v) => setF({ ...f, systolic: v })} unit="mmHg" /></Field>
          <Field id="w-dia" label="Blood pressure, bottom number" hint={latest.diastolic ? `Latest saved: ${latest.diastolic}` : undefined}><NumberInput id="w-dia" value={f.diastolic} onChange={(v) => setF({ ...f, diastolic: v })} unit="mmHg" /></Field>
          <Field id="w-chol" label="Total cholesterol" hint={latest.cholesterol ? `Latest saved: ${latest.cholesterol}` : undefined}><NumberInput id="w-chol" value={f.cholesterol} onChange={(v) => setF({ ...f, cholesterol: v })} unit="mg/dL" /></Field>
          <Field id="w-glu" label="Fasting blood sugar" hint={latest.glucose ? `Latest saved: ${latest.glucose}` : undefined}><NumberInput id="w-glu" value={f.glucose} onChange={(v) => setF({ ...f, glucose: v })} unit="mg/dL" /></Field>
          <Field id="w-wt" label="Weight" hint={latest.weight ? `Latest saved: ${latest.weight}` : undefined}><NumberInput id="w-wt" value={f.weight} onChange={(v) => setF({ ...f, weight: v })} unit="kg" /></Field>
          <Field id="w-act" label="Brisk activity per week" hint="Total minutes"><NumberInput id="w-act" value={f.activity} onChange={(v) => setF({ ...f, activity: v })} unit="min" step={1} /></Field>
        </div>
        <div className="checks">
          <label className="check"><input type="checkbox" checked={f.save} onChange={(e) => setF({ ...f, save: e.target.checked })} /><span>Save these values to my measurement history</span></label>
          <label className="check"><input type="checkbox" checked={f.southAsian} onChange={(e) => setF({ ...f, southAsian: e.target.checked })} /><span>Use South Asian BMI cut-offs</span></label>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" onClick={() => { setError(""); submit.mutate(); }} disabled={submit.isPending}>{submit.isPending ? "Reviewing…" : "Review my risk factors"}</button></div>
      </Card>
    </div>
  );
}
