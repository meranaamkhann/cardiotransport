import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { ModelCard } from "../../api/types";
import { CalibrationPlot, GroupedBars } from "../../components/charts";
import { ErrorState, Notice, Pct, Spinner } from "../../components/ui";

const SITES = ["Cleveland", "Hungary", "Switzerland", "Long Beach VA"];
const bandName = { lower: "Lower concern", moderate: "Worth getting checked", higher: "See a doctor soon" } as const;

export default function HowItWorks() {
  const { data: card, error, isLoading, refetch } = useQuery({ queryKey: ["card"], queryFn: () => api<ModelCard>("/model-card") });
  if (isLoading) return <Spinner />;
  if (error || !card) return <ErrorState error={error} retry={() => void refetch()} />;
  const clinical = card.deployment.clinical;
  const core = card.deployment.core;
  const zero = Object.values(card.zero_values_recoded_as_missing).reduce((s, v) => s + v.chol, 0);
  return (
    <div className="stack">
      <h1>How CardioLens works</h1>
      {card.data_source !== "uci" && <Notice tone="warn" title="Demonstration build">The figures below come from generated demo data.</Notice>}
      <section className="card">
        <h2>Three separate layers</h2>
        <ol>
          <li><strong>Symptom triage</strong> uses transparent rules. Emergency warning signs always produce emergency guidance.</li>
          <li><strong>A research model</strong> compares your answers with {Object.values(card.cohorts).reduce((s, c) => s + c.n, 0)} angiography-referred patients from four hospitals. It can raise the urgency but never lower it. Every score comes with a plausible range from {clinical.bootstrap_models} resampled models, and a second, differently built model (a random forest) flags when it disagrees.</li>
          <li><strong>Clinician review</strong> is written by a person and labelled as such.</li>
        </ol>
        <p className="muted">The model is a regularised logistic regression. It stays interpretable, and its probabilities are better calibrated than a random forest&apos;s. Its explanations are exact linear contributions, which equal SHAP values for a linear model.</p>
      </section>
      <section className="card">
        <h2>Ranking ability on hospitals it never saw (AUC)</h2>
        <GroupedBars label="AUC by held-out hospital" domain={[0.4, 1]} keys={["Simple model", "Detailed model"]}
          data={SITES.map((s) => ({ name: s, "Simple model": core.held_out_site[s]?.auc ?? null, "Detailed model": clinical.held_out_site[s]?.auc ?? null }))} />
        <p className="muted">The two models agree on the risk band for {clinical.agreement.same_band_pct}% of held-out records. Each bar comes from training on three hospitals and testing on the fourth. 1.0 is perfect and 0.5 is a coin flip. The spread is the message: one accuracy number would hide it.</p>
      </section>
      <section className="card">
        <h2>Do the scores mean what they say?</h2>
        <CalibrationPlot curves={Object.fromEntries(SITES.map((s) => [s, clinical.calibration[s]]))} />
        <p className="muted">Lines near the dashed diagonal are well calibrated. Hospitals with very different disease rates sit far above or below it, which is why CardioLens reports bands and observed rates instead of one percentage.</p>
      </section>
      <section className="card">
        <h2>What each band has meant in the records</h2>
        <div className="scroll"><table className="plain wide"><thead><tr><th>Band</th><th>People</th><th>Had blockage</th><th>Range across hospitals</th></tr></thead>
          <tbody>{(["lower", "moderate", "higher"] as const).map((b) => { const s = clinical.bands.stats[b]; return <tr key={b}><td>{bandName[b]}</td><td>{s.n}</td><td><Pct value={s.rate} /></td><td><Pct value={s.site_min} /> to <Pct value={s.site_max} /></td></tr>; })}</tbody></table></div>
        <p className="muted">Cut-offs are chosen so the lower band still holds only about 10% of people who had blockage, and the higher band keeps false alarms among people without blockage near 15%.</p>
      </section>
      <section className="card">
        <h2>Data quality</h2>
        <p>{zero} records had a cholesterol of exactly 0, which is physiologically impossible and means not measured. The deployed model treats them as missing.</p>
      </section>
      <section className="card">
        <h2>Limits you should know</h2>
        <ul>
          <li>The records are from the 1980s and every patient was already referred for angiography. They do not describe the general public.</li>
          <li>The model estimates narrowed arteries on angiography, not the chance of a heart attack. It is not a screening test or a medical device.</li>
          <li>Patients without chest pain who were referred anyway often had blockage, because they were sent for abnormal tests. That is why people without symptoms get a risk-factor review instead of a model estimate.</li>
          <li>Few external records were from women or young people, so the model is least reliable for them.</li>
        </ul>
        <p className="muted small">Model version {card.version}, trained {new Date(card.trained_at).toLocaleDateString()}.</p>
      </section>
    </div>
  );
}
