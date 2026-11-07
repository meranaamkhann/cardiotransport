import { saveWellness } from "../platformApi";
import { getSession } from "../session";
import { useState } from "react";
import { wellness } from "../api";
import type { WellnessPayload, WellnessResult } from "../types";
import { Choices, Field, Notice, NumberInput } from "../ui";

const num = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

export default function Wellness({ onResult }: { onResult: (r: WellnessResult, subtitle: string) => void }) {
  const [f, setF] = useState({
    age: "", sex: "" as "" | "female" | "male", systolic: "", diastolic: "", cholesterol: "", glucose: "",
    height: "", weight: "", smoking: "" as "" | "never" | "former" | "current", activity: "",
    diabetes: false, family: false, southAsian: true,
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v }));

  const submit = async () => {
    const age = num(f.age);
    if (age === null || age < 18 || age > 100) return setError("Enter your age (18 to 100).");
    if (!f.sex) return setError("Choose your sex at birth.");
    if (!f.smoking) return setError("Tell us about smoking.");
    const payload: WellnessPayload = {
      age, sex: f.sex, systolic: num(f.systolic), diastolic: num(f.diastolic), cholesterol: num(f.cholesterol),
      fasting_glucose: num(f.glucose), height_cm: num(f.height), weight_kg: num(f.weight), smoking: f.smoking,
      diabetes: f.diabetes, family_history: f.family, activity_minutes: num(f.activity), south_asian_cutoffs: f.southAsian,
    };
    setError("");
    setBusy(true);
    try {
      const account = getSession();
      onResult(account?.role === "patient" ? (await saveWellness(payload)).result : await wellness(payload), `${age} y, ${f.sex}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  };

  return (
    <div className="wizard card">
      <h2>Your heart risk factors</h2>
      <p className="hint">Fill in what you know. Blank fields are fine.</p>
      <div className="grid2">
        <Field id="w-age" label="Age"><NumberInput id="w-age" value={f.age} onChange={(v) => set("age", v)} unit="years" min={18} max={100} step={1} /></Field>
        <Field id="w-sex" label="Sex at birth">
          <Choices name="Sex" value={f.sex} onChange={(v) => set("sex", v)} options={[{ value: "female", title: "Female" }, { value: "male", title: "Male" }]} />
        </Field>
      </div>
      <div className="grid2">
        <Field id="w-sys" label="Blood pressure, top number"><NumberInput id="w-sys" value={f.systolic} onChange={(v) => set("systolic", v)} unit="mmHg" /></Field>
        <Field id="w-dia" label="Blood pressure, bottom number"><NumberInput id="w-dia" value={f.diastolic} onChange={(v) => set("diastolic", v)} unit="mmHg" /></Field>
        <Field id="w-chol" label="Total cholesterol"><NumberInput id="w-chol" value={f.cholesterol} onChange={(v) => set("cholesterol", v)} unit="mg/dL" /></Field>
        <Field id="w-glu" label="Fasting blood sugar"><NumberInput id="w-glu" value={f.glucose} onChange={(v) => set("glucose", v)} unit="mg/dL" /></Field>
        <Field id="w-h" label="Height"><NumberInput id="w-h" value={f.height} onChange={(v) => set("height", v)} unit="cm" /></Field>
        <Field id="w-w" label="Weight"><NumberInput id="w-w" value={f.weight} onChange={(v) => set("weight", v)} unit="kg" /></Field>
      </div>
      <Field id="w-smoke" label="Smoking">
        <Choices name="Smoking" value={f.smoking} onChange={(v) => set("smoking", v)}
          options={[{ value: "never", title: "Never" }, { value: "former", title: "Former" }, { value: "current", title: "Current" }]} />
      </Field>
      <Field id="w-act" label="Brisk physical activity per week" hint="Walking fast, cycling, sports. Total minutes.">
        <NumberInput id="w-act" value={f.activity} onChange={(v) => set("activity", v)} unit="min" min={0} step={1} />
      </Field>
      <div className="checks">
        <label className="check"><input type="checkbox" checked={f.diabetes} onChange={(e) => set("diabetes", e.target.checked)} /><span>I have diabetes</span></label>
        <label className="check"><input type="checkbox" checked={f.family} onChange={(e) => set("family", e.target.checked)} /><span>A parent or sibling had heart disease early (men under 55, women under 65)</span></label>
        <label className="check"><input type="checkbox" checked={f.southAsian} onChange={(e) => set("southAsian", e.target.checked)} /><span>Use South Asian BMI cut-offs</span></label>
      </div>
      {error && <Notice tone="warn">{error}</Notice>}
      <div className="actions">
        <button className="btn primary" onClick={() => void submit()} disabled={busy}>{busy ? "Working…" : "Check my risk factors"}</button>
      </div>
    </div>
  );
}
