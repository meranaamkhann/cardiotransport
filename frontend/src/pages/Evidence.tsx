import { useEffect, useState } from "react";
import { modelCard } from "../api";
import { CalibrationChart, GroupedBars } from "../charts";
import type { ModelCard } from "../types";
import { Notice, Pct } from "../ui";

const SITES = ["Cleveland", "Hungary", "Switzerland", "Long Beach VA"];
const bandName = { lower: "Lower concern", moderate: "Worth getting checked", higher: "See a doctor soon" } as const;

export default function Evidence() {
  const [card, setCard] = useState<ModelCard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { modelCard().then(setCard).catch((e: Error) => setError(e.message)); }, []);
  if (error) return <Notice tone="warn">{error}</Notice>;
  if (!card) return <p className="muted">Loading…</p>;

  const clinical = card.deployment.clinical;
  const core = card.deployment.core;
  const paper = card.paper_protocol?.portable10_logistic;
  const zeroTotal = Object.values(card.zero_values_recoded_as_missing).reduce((s, v) => s + v.chol, 0);

  return (
    <div className="stack">
      {card.data_source !== "uci" && <Notice tone="warn" title="Demonstration build">The figures below come from generated demo data.</Notice>}
      <section className="card">
        <h2>How it works</h2>
        <ol>
          <li>The model learns from {Object.values(card.cohorts).reduce((s, c) => s + c.n, 0)} angiography-referred patients at four hospitals (Cleveland, Hungary, Switzerland, Long Beach VA).</li>
          <li>It is a regularised logistic regression, chosen because it stays interpretable and its probabilities stay better calibrated than a random forest.</li>
          <li>Every accuracy figure here is from <strong>leave-one-hospital-out testing</strong>: the model is trained on three hospitals and tested on the fourth, which it never saw.</li>
          <li>Results are shown as bands, with the share of similar patients who really had blockage, because probabilities do not transfer between hospitals.</li>
        </ol>
      </section>

      <section className="card">
        <h2>Ranking ability on unseen hospitals (AUC)</h2>
        <GroupedBars label="AUC by held-out hospital" categories={SITES}
          series={[
            { name: "Simple model (7 inputs)", values: SITES.map((s) => core.held_out_site[s]?.auc ?? null) },
            { name: "Detailed model (10 inputs)", values: SITES.map((s) => clinical.held_out_site[s]?.auc ?? null) },
          ]} />
        <p className="muted">1.0 is perfect and 0.5 is a coin flip. The spread between hospitals is the real message: a single accuracy number hides it.</p>
      </section>

      <section className="card">
        <h2>Do the scores mean what they say?</h2>
        <CalibrationChart label="Calibration of the detailed model on unseen hospitals" curves={Object.fromEntries(SITES.map((s) => [s, clinical.calibration[s]]))} />
        <p className="muted">Lines near the dashed diagonal are well calibrated. Hospitals with very different disease rates sit far above or below it, which is why this tool reports bands and observed rates instead of a single percentage.</p>
      </section>

      <section className="card">
        <h2>What each band has meant in the records</h2>
        <div className="scroll">
          <table className="plain wide">
            <thead><tr><th>Band</th><th>People</th><th>Had blockage</th><th>Range across hospitals</th></tr></thead>
            <tbody>
              {(["lower", "moderate", "higher"] as const).map((b) => {
                const s = clinical.bands.stats[b];
                return <tr key={b}><td>{bandName[b]}</td><td>{s.n}</td><td><Pct value={s.rate} /></td><td><Pct value={s.site_min} /> to <Pct value={s.site_max} /></td></tr>;
              })}
            </tbody>
          </table>
        </div>
        <p className="muted">Band cut-offs are set so the lower band still contains only about 10% of people who had blockage, and the higher band keeps false alarms among healthy people near 15%.</p>
      </section>

      {paper && (
        <section className="card">
          <h2>Original study protocol (train on Cleveland only)</h2>
          <div className="scroll">
            <table className="plain wide">
              <thead><tr><th>Test set</th><th>AUC</th><th>Calibration slope</th><th>Calibration intercept</th></tr></thead>
              <tbody>
                <tr><td>Cleveland, cross-validated</td><td>{paper.internal.auc}</td><td>{paper.internal.cal_slope}</td><td>{paper.internal.cal_intercept}</td></tr>
                {Object.entries(paper.external).map(([site, m]) => <tr key={site}><td>{site}</td><td>{m.auc}</td><td>{m.cal_slope}</td><td>{m.cal_intercept}</td></tr>)}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card">
        <h2>Data quality</h2>
        <p>{zeroTotal} records had a cholesterol of exactly 0, which is impossible and means "not measured". They are treated as missing, not as real values.</p>
        <div className="scroll">
          <table className="plain wide">
            <thead><tr><th>Hospital</th><th>Patients</th><th>Disease rate</th><th>Median age</th><th>Women</th><th>Zero cholesterol</th></tr></thead>
            <tbody>
              {SITES.map((s) => {
                const c = card.cohorts[s];
                return <tr key={s}><td>{s}</td><td>{c.n}</td><td><Pct value={c.prevalence} /></td><td>{c.median_age}</td><td>{c.female_pct}%</td><td>{card.zero_values_recoded_as_missing[s]?.chol ?? 0}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Limits you should know</h2>
        <ul>
          <li>The records are from the 1980s, and every patient was already referred for angiography. They are not a picture of the general public.</li>
          <li>In these records, patients with no chest pain who were referred anyway often had blockage, because they were sent for abnormal tests. That is why "no chest pain" is only offered to people who were referred.</li>
          <li>Only 97 external records were female and few were young, so the tool is least reliable for women and for people under 40.</li>
          <li>It estimates narrowed arteries on angiography, not the chance of a heart attack, and it is not a screening test or a medical device.</li>
        </ul>
        <p className="muted">Model version {card.version}, trained {new Date(card.trained_at).toLocaleDateString()}.</p>
      </section>
    </div>
  );
}
