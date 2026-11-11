import type { ReactNode } from "react";
import type { AssessmentRecord } from "../api/types";
import { ModelSections, WellnessSections } from "./ModelResult";
import { LevelBadge, Notice, Provenance, when } from "./ui";

const LABEL: Record<string, string> = {
  chest_discomfort: "Chest discomfort", discomfort_with_effort: "Brought on by effort", breathlessness: "Breathlessness", palpitations: "Palpitations",
  dizziness: "Dizziness", fatigue: "Fatigue", duration: "Duration", severity: "Severity (1 to 10)", emergency: "Warning signs reported", conditions: "Medical history",
  systolic: "Systolic pressure", diastolic: "Diastolic pressure", cholesterol: "Cholesterol", fasting_glucose: "Fasting glucose", ecg: "Resting ECG", max_hr: "Peak heart rate",
  st_depression: "ST depression", age: "Age", sex: "Sex", weight_kg: "Weight", activity_minutes: "Activity (min/week)",
};

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.join(", ").replace(/_/g, " ") : "None";
  return String(value).replace(/_/g, " ");
}

export default function AssessmentView({ a, actions, review }: { a: AssessmentRecord; actions?: ReactNode; review?: ReactNode }) {
  const result = a.result;
  if (!result) return null;
  const inputs = Object.entries(a.inputs ?? {}).filter(([k]) => k !== "save_measurements" && k !== "south_asian_cutoffs" && k !== "autofilled_from_history");
  const filled = (a.inputs?.autofilled_from_history as string[] | undefined) ?? [];
  return (
    <div className="result">
      <div className="card">
        <div className="card-head">
          <div>
            <p className="eyebrow">{a.kind === "symptom" ? "Symptom assessment" : "Wellness assessment"} · #{a.id}</p>
            <h2>{a.kind === "symptom" ? result.final.title : result.headline}</h2>
            <p className="muted">{when(a.created_at)}{a.patient_name ? ` · ${a.patient_name}` : ""}</p>
          </div>
          <LevelBadge level={a.urgency} />
        </div>
        {a.kind === "symptom" && <p>{result.final.message}</p>}
        {a.kind === "symptom" && <p className="muted small">{result.final.rule}</p>}
        <div className="actions no-print">{actions}</div>
      </div>

      {a.kind === "symptom" && result.triage.level === "emergency" && (
        <Notice tone="danger" title="Emergency guidance">{result.triage.message}</Notice>
      )}

      <section className="card">
        <div className="card-head"><h3>Patient-reported information</h3><Provenance kind="reported">Entered by the patient</Provenance></div>
        <table className="plain"><tbody>
          {inputs.map(([k, v]) => <tr key={k}><th>{LABEL[k] ?? k.replace(/_/g, " ")}</th><td>{show(v)}</td></tr>)}
        </tbody></table>
        {filled.length > 0 && <p className="muted small">Filled from the patient&apos;s own measurement history: {filled.join(", ").replace(/_/g, " ")}.</p>}
      </section>

      {a.kind === "symptom" ? (
        <>
          <section className="card">
            <div className="card-head"><h3>Symptom triage</h3><Provenance kind="model">Rule-based, not a diagnosis</Provenance></div>
            <ul>{result.triage.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            <p className="muted small">{result.triage.limits}</p>
          </section>
          {result.model ? (
            <div className="stack-tight">
              <div className="provenance-bar"><Provenance kind="model">Model-generated</Provenance> Research model trained on historical angiography records. Not clinically validated.</div>
              <ModelSections r={result.model} />
            </div>
          ) : <Notice tone="info" title="No model estimate">{result.model_note}</Notice>}
        </>
      ) : (
        <div className="stack-tight">
          <div className="provenance-bar"><Provenance kind="model">Guideline review</Provenance> Published cut-offs applied to the values above. Not a prediction or a diagnosis.</div>
          <WellnessSections r={result} />
        </div>
      )}

      <section className="card">
        <div className="card-head"><h3>Clinician review</h3><Provenance kind="clinician">{a.status === "reviewed" ? "Written by a clinician" : "Awaiting review"}</Provenance></div>
        {a.status === "reviewed" ? (
          <>
            <p>{a.clinician_summary}</p>
            <p className="muted small">Reviewed by {a.reviewer} on {a.reviewed_at ? when(a.reviewed_at) : ""}</p>
          </>
        ) : <p className="muted">No clinician has reviewed this assessment yet.</p>}
        {review}
      </section>
    </div>
  );
}
