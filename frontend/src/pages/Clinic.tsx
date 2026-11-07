import { useState } from "react";
import { calibrateClinic } from "../api";
import { loadCalibrations, saveCalibrations } from "../storage";
import type { Calibration, ClinicResult } from "../types";
import { Notice } from "../ui";

const methodText = { none: "no change", intercept: "baseline shift only", slope: "baseline shift and spread" } as const;

export default function Clinic() {
  const [file, setFile] = useState<File | null>(null);
  const [site, setSite] = useState("");
  const [result, setResult] = useState<ClinicResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState<Calibration[]>(loadCalibrations());

  const run = async () => {
    if (!file) return setError("Choose a CSV file first.");
    setBusy(true);
    setError("");
    try {
      setResult(await calibrateClinic(file, site));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
    setBusy(false);
  };

  const apply = () => {
    if (!result) return;
    const items = result.results.map((t) => ({ tier: t.tier, intercept: t.intercept, slope: t.slope, label: result.site_name || "your clinic", n: t.n }));
    saveCalibrations(items);
    setActive(items);
  };

  return (
    <div className="stack">
      <section className="card">
        <h2>Calibrate for your clinic</h2>
        <p>
          A model learned at one hospital often over- or under-estimates risk at another, because patient mix differs. With a small
          set of your own labelled cases, CardioLens can shift its estimates to match your local rate. Ranking quality stays the same.
        </p>
        <ul>
          <li>At least 40 patients with a known angiography result, with at least 10 who had disease and 10 who did not.</li>
          <li>Columns: age, sex (1 male), cp (1 to 4), exang, trestbps, chol, fbs, optional restecg, thalach, oldpeak, and outcome (0 or 1).</li>
          <li>The file is processed in memory and never stored. Only two numbers are kept, on this device.</li>
        </ul>
        <p><a href="/api/clinic/template" download>Download the CSV template</a></p>
        <div className="grid2">
          <div className="field"><label htmlFor="site">Clinic or hospital name</label><input id="site" value={site} maxLength={80} onChange={(e) => setSite(e.target.value)} /></div>
          <div className="field"><label htmlFor="csv">Labelled cases (CSV)</label><input id="csv" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        <div className="actions"><button className="btn primary" onClick={() => void run()} disabled={busy}>{busy ? "Calibrating…" : "Calibrate"}</button></div>
      </section>

      {result && (
        <section className="card">
          <h3>Result from {result.n} patients ({result.events} with disease)</h3>
          {result.results.map((t) => (
            <div key={t.tier} className="tier-result">
              <h4>{t.tier === "core" ? "Simple model" : "Detailed model"}: {methodText[t.method]}</h4>
              <p>Your observed disease rate is {Math.round(t.observed_rate * 100)}%, while the unadjusted model averaged {Math.round(t.mean_predicted_before * 100)}%.</p>
              <p>Estimated probability error (Brier, cross-validated): {t.brier_before} before, {t.brier_after} after.</p>
              {!t.slope_update_considered && <p className="muted">A spread adjustment needs at least 100 patients, so only the baseline was shifted.</p>}
            </div>
          ))}
          <div className="actions"><button className="btn primary" onClick={apply}>Use on this device</button></div>
        </section>
      )}

      {active.length > 0 && (
        <Notice tone="good" title={`Calibration active: ${active[0].label}`}>
          New checks on this device will also show a locally adjusted estimate.{" "}
          <button className="linklike inline" onClick={() => { saveCalibrations([]); setActive([]); }}>Remove</button>
        </Notice>
      )}
    </div>
  );
}
