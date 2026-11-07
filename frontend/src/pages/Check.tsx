import { useState } from "react";
import { assess } from "../api";
import { loadCalibrations } from "../storage";
import type { AssessmentPayload, AssessmentResult, Pathway } from "../types";
import { Choices, Field, Notice, NumberInput } from "../ui";

interface Form {
  emergency: string[];
  age: string;
  sex: "" | "female" | "male";
  chestPain: "" | "typical" | "atypical" | "non_anginal" | "none";
  exercisePain: "" | "yes" | "no";
  systolic: string;
  cholesterol: string;
  glucose: string;
  hasReports: boolean;
  ecg: "" | "normal" | "st_t_abnormality" | "lv_hypertrophy";
  maxHr: string;
  stDepression: string;
}

const blank: Form = {
  emergency: [], age: "", sex: "", chestPain: "", exercisePain: "", systolic: "", cholesterol: "", glucose: "",
  hasReports: false, ecg: "", maxHr: "", stDepression: "",
};

const warnings = [
  { key: "pain_at_rest", text: "Chest pain or pressure that started at rest and has lasted more than 15 minutes" },
  { key: "pain_spreading", text: "Pain spreading to the arm, shoulder, jaw, or back, with sweating or nausea" },
  { key: "fainting", text: "Fainting or nearly fainting" },
  { key: "sudden_breathlessness", text: "Sudden, severe shortness of breath" },
];

const stepNames = ["Safety first", "About you", "Your chest pain", "Your numbers", "Test reports"];

const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

export default function Check({ pathway, onResult }: { pathway: Pathway; onResult: (r: AssessmentResult) => void }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Form>(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));

  const painOptions = [
    { value: "typical" as const, title: "Pressure or tightness with effort", text: "A squeezing or heavy feeling in the chest that comes with effort or stress and eases within minutes of rest." },
    { value: "atypical" as const, title: "Some of those features", text: "Chest discomfort that has part of that pattern, such as lasting longer or coming at odd times." },
    { value: "non_anginal" as const, title: "Chest pain that does not fit", text: "Sharp or pinpoint pain, pain that changes with breathing or posture, or clearly muscular pain." },
    ...(pathway === "referred"
      ? [{ value: "none" as const, title: "No chest pain", text: "I was sent for a heart check for another reason, such as an abnormal test." }]
      : []),
  ];

  const validate = (): string => {
    if (step === 1) {
      const age = num(form.age);
      if (age === null || age < 18 || age > 100) return "Enter your age (18 to 100).";
      if (!form.sex) return "Choose the option that matches your sex at birth.";
    }
    if (step === 2) {
      if (!form.chestPain) return "Pick the description that fits best.";
      if (!form.exercisePain) return "Tell us whether effort brings on chest pain or tightness.";
    }
    if (step === 3) {
      const checks: [string, number | null, number, number][] = [
        ["Blood pressure", num(form.systolic), 70, 260],
        ["Cholesterol", num(form.cholesterol), 80, 700],
        ["Fasting blood sugar", num(form.glucose), 40, 700],
      ];
      for (const [name, value, low, high] of checks) {
        if (value !== null && (value < low || value > high)) return `${name} should be between ${low} and ${high}. Leave it blank if you are unsure.`;
      }
    }
    if (step === 4 && form.hasReports) {
      const hr = num(form.maxHr), st = num(form.stDepression);
      if (hr !== null && (hr < 60 || hr > 230)) return "Highest heart rate should be between 60 and 230.";
      if (st !== null && (st < -3 || st > 8)) return "ST depression should be between -3 and 8.";
    }
    return "";
  };

  const submit = async () => {
    const payload: AssessmentPayload = {
      pathway,
      age: Number(form.age),
      sex: form.sex as "female" | "male",
      chest_pain: form.chestPain as AssessmentPayload["chest_pain"],
      exercise_pain: form.exercisePain === "yes",
      systolic: num(form.systolic),
      cholesterol: num(form.cholesterol),
      fasting_glucose: num(form.glucose),
      ecg: form.hasReports && form.ecg ? form.ecg : null,
      max_hr: form.hasReports ? num(form.maxHr) : null,
      st_depression: form.hasReports ? num(form.stDepression) : null,
      emergency: form.emergency,
      local_calibrations: loadCalibrations(),
    };
    setBusy(true);
    try {
      onResult(await assess(payload));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  };

  const next = () => {
    const problem = validate();
    setError(problem);
    if (problem) return;
    if (step === stepNames.length - 1) void submit();
    else setStep(step + 1);
  };

  const back = () => {
    setError("");
    setStep(Math.max(0, step - 1));
  };

  return (
    <div className="wizard card">
      <div className="progress" aria-label={`Step ${step + 1} of ${stepNames.length}`}>
        <div style={{ width: `${((step + 1) / stepNames.length) * 100}%` }} />
      </div>
      <p className="step-label">Step {step + 1} of {stepNames.length} · {stepNames[step]}</p>

      {step === 0 && (
        <>
          <h2>Are you having any of these right now?</h2>
          <div className="checks">
            {warnings.map((w) => (
              <label key={w.key} className="check">
                <input type="checkbox" checked={form.emergency.includes(w.key)}
                  onChange={(e) => set("emergency", e.target.checked ? [...form.emergency, w.key] : form.emergency.filter((k) => k !== w.key))} />
                <span>{w.text}</span>
              </label>
            ))}
          </div>
          {form.emergency.length > 0 && (
            <Notice tone="danger" title="Get emergency help now">
              These can be signs of a heart attack. Call your local emergency number (112 in India, 911 in the US, 999 in the UK) and do not drive yourself.
              <div className="actions"><a className="btn danger" href="tel:112">Call 112</a></div>
            </Notice>
          )}
          <p className="hint">If none apply, continue. You can still complete the check.</p>
        </>
      )}

      {step === 1 && (
        <>
          <h2>Tell us about you</h2>
          <Field id="age" label="Age">
            <NumberInput id="age" value={form.age} onChange={(v) => set("age", v)} unit="years" min={18} max={100} step={1} />
          </Field>
          <Field id="sex" label="Sex at birth" hint="The reference data records sex as male or female, so this is the closest fit.">
            <Choices name="Sex at birth" value={form.sex} onChange={(v) => set("sex", v)}
              options={[{ value: "female", title: "Female" }, { value: "male", title: "Male" }]} />
          </Field>
        </>
      )}

      {step === 2 && (
        <>
          <h2>Describe your chest pain</h2>
          <p className="hint">Choose the closest match. A doctor decides the exact type.</p>
          <Choices name="Chest pain" value={form.chestPain} onChange={(v) => set("chestPain", v)} options={painOptions} />
          <Field id="exercise" label="Does physical effort, such as stairs or a brisk walk, bring on chest pain or tightness?">
            <Choices name="Effort pain" value={form.exercisePain} onChange={(v) => set("exercisePain", v)}
              options={[{ value: "yes", title: "Yes" }, { value: "no", title: "No" }]} />
          </Field>
        </>
      )}

      {step === 3 && (
        <>
          <h2>Your numbers</h2>
          <p className="hint">Use your latest readings. If you do not know one, leave it blank; it only lowers how confident the result is.</p>
          <Field id="systolic" label="Resting blood pressure, top number" hint="For 130/85, enter 130.">
            <NumberInput id="systolic" value={form.systolic} onChange={(v) => set("systolic", v)} unit="mmHg" min={70} max={260} />
          </Field>
          <Field id="chol" label="Total cholesterol" hint="From a lipid profile. If your report is in mmol/L, multiply by 38.7.">
            <NumberInput id="chol" value={form.cholesterol} onChange={(v) => set("cholesterol", v)} unit="mg/dL" min={80} max={700} />
          </Field>
          <Field id="glucose" label="Fasting blood sugar" hint="If your report is in mmol/L, multiply by 18.">
            <NumberInput id="glucose" value={form.glucose} onChange={(v) => set("glucose", v)} unit="mg/dL" min={40} max={700} />
          </Field>
        </>
      )}

      {step === 4 && (
        <>
          <h2>Do you have an ECG or stress-test report?</h2>
          <label className="check">
            <input type="checkbox" checked={form.hasReports} onChange={(e) => set("hasReports", e.target.checked)} />
            <span>Yes, I have a recent ECG and exercise stress-test report</span>
          </label>
          {form.hasReports ? (
            <>
              <p className="hint">Enter all three to use the more detailed model. Anything missing falls back to the simpler one.</p>
              <Field id="ecg" label="Resting ECG result">
                <select id="ecg" value={form.ecg} onChange={(e) => set("ecg", e.target.value as Form["ecg"])}>
                  <option value="">Select</option>
                  <option value="normal">Normal</option>
                  <option value="st_t_abnormality">ST-T wave abnormality</option>
                  <option value="lv_hypertrophy">Left ventricular hypertrophy</option>
                </select>
              </Field>
              <Field id="maxhr" label="Highest heart rate reached in the stress test">
                <NumberInput id="maxhr" value={form.maxHr} onChange={(v) => set("maxHr", v)} unit="bpm" min={60} max={230} />
              </Field>
              <Field id="st" label="ST depression during the stress test" hint="Often written as ST depression or oldpeak, in millimetres.">
                <NumberInput id="st" value={form.stDepression} onChange={(v) => set("stDepression", v)} unit="mm" min={-3} max={8} step={0.1} />
              </Field>
            </>
          ) : (
            <p className="hint">No problem. You will get a result from the simpler model.</p>
          )}
        </>
      )}

      {error && <Notice tone="warn">{error}</Notice>}

      <div className="actions between">
        <button className="btn ghost" onClick={back} disabled={step === 0 || busy}>Back</button>
        <button className="btn primary" onClick={next} disabled={busy}>
          {busy ? "Working…" : step === stepNames.length - 1 ? "See my result" : "Continue"}
        </button>
      </div>
    </div>
  );
}
