import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download } from "../../api/client";
import type { Experiment, Metrics } from "../../api/types";
import { CalibrationPlot, DecisionPlot, GroupedBars, Heatmap, HorizontalBars, RocChart } from "../../components/charts";
import { Card, EmptyState, ErrorState, Notice, Provenance, Spinner, Tabs } from "../../components/ui";
import { provenanceBadge } from "./Experiments";

type Tab = "overview" | "performance" | "roc" | "calibration" | "decision" | "missing" | "features" | "subgroups" | "recalibration";

const fmt = (v: number | null | undefined, d = 3) => (v === null || v === undefined ? "n/a" : v.toFixed(d));
const withCi = (m: Metrics) => `${fmt(m.auc)}${m.auc_ci ? ` (${fmt(m.auc_ci[0])}–${fmt(m.auc_ci[1])})` : ""}`;
const pretty = (s: string) => s.replace(/_/g, " ");

export default function ExperimentDashboard() {
  const { id } = useParams();
  const [tab, setTab] = useState<Tab>("overview");
  const [model, setModel] = useState("portable_logistic");
  const [site, setSite] = useState("");
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ["experiment", id], queryFn: () => api<Experiment>(`/research/experiments/${id}`),
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "queued" || q.state.data.status === "running") ? 2000 : false),
  });
  if (isLoading) return <Spinner label="Loading experiment" />;
  if (error || !data) return <ErrorState error={error} retry={() => void refetch()} />;

  const head = (
    <div className="row between">
      <div><Link to="/research" className="no-print">← Experiments</Link><h1>{data.name}</h1><p>{provenanceBadge(data.provenance)}</p></div>
      {data.status === "completed" && <div className="row">
        <button className="btn ghost small" onClick={() => void download(`/research/experiments/${data.id}/report.csv`, `cardiolens-experiment-${data.id}.csv`)}>CSV</button>
        <button className="btn primary small" onClick={() => void download(`/research/experiments/${data.id}/report.pdf`, `cardiolens-experiment-${data.id}.pdf`)}>PDF report</button></div>}
    </div>
  );
  if (data.status === "queued" || data.status === "running") {
    return <div className="stack">{head}<Card><p><progress max={1} value={data.progress} /> {Math.round(data.progress * 100)}%</p><p className="muted">{data.stage}. This page updates by itself.</p></Card></div>;
  }
  if (data.status === "failed" || !data.result) {
    return <div className="stack">{head}<Notice tone="warn" title="This experiment did not complete">{data.error ?? "No result was produced."}</Notice></div>;
  }

  const r = data.result;
  const models = Object.keys(r.models);
  const selected = r.models[model] ?? r.models[models[0]];
  const activeModel = r.models[model] ? model : models[0];
  const sites = r.sites_external;
  const siteKey = sites.includes(site) ? site : sites[0];
  const cohorts = [r.dev_site, ...sites];

  return (
    <div className="stack">
      {head}
      {r.meta.data_source !== "uci" && data.provenance !== "new_experiment" && <Notice tone="warn" title="Synthetic data">These figures describe generated records, not real patients.</Notice>}
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "overview", label: "Overview" }, { id: "performance", label: "Performance" }, { id: "roc", label: "ROC" }, { id: "calibration", label: "Calibration" },
        { id: "decision", label: "Decision curves" }, { id: "missing", label: "Missing data" }, { id: "features", label: "Features" },
        { id: "subgroups", label: "Subgroups" }, { id: "recalibration", label: "Recalibration" }]} />
      {["roc", "calibration", "decision", "features"].includes(tab) && (
        <div className="row">
          <label className="muted small" htmlFor="model">Model</label>
          <select id="model" value={activeModel} onChange={(e) => setModel(e.target.value)}>{models.map((m) => <option key={m} value={m}>{pretty(m)}</option>)}</select>
          {tab === "decision" && <><label className="muted small" htmlFor="site">Cohort</label><select id="site" value={siteKey} onChange={(e) => setSite(e.target.value)}>{sites.map((s) => <option key={s}>{s}</option>)}</select></>}
        </div>
      )}

      {tab === "overview" && (
        <>
          <Card title="Experiment">
            <table className="plain"><tbody>
              <tr><th>Type</th><td>{r.meta.provenance_label}</td></tr><tr><th>Data</th><td>{r.meta.data_source}</td></tr>
              <tr><th>Development cohort</th><td>{r.dev_site}</td></tr><tr><th>Cross-validation</th><td>{r.meta.folds}-fold × {r.meta.repeats} repeats</td></tr>
              <tr><th>Bootstrap resamples</th><td>{r.meta.bootstrap}</td></tr><tr><th>Zero cholesterol / BP</th><td>{r.meta.recode_zeros ? "recoded as missing" : "kept as recorded"}</td></tr>
            </tbody></table>
          </Card>
          <Card title="Cohorts"><div className="scroll"><table className="plain"><thead><tr><th>Cohort</th><th>Records</th><th>With disease</th><th>Prevalence</th></tr></thead>
            <tbody>{cohorts.map((c) => <tr key={c}><td>{c}{c === r.dev_site ? " (development)" : ""}</td><td>{r.cohorts[c].n}</td><td>{r.cohorts[c].events}</td><td>{fmt(r.cohorts[c].prevalence)}</td></tr>)}</tbody></table></div></Card>
          <Card title={`Does ${pretty(r.verdict_model)} transport?`} action={<Provenance kind="extension">Rules of thumb</Provenance>}>
            <ul className="list">{r.verdicts.map((v) => <li key={v.site}><div><strong>{v.site}</strong><span className="muted small">{v.status}</span></div><span className={`badge ${v.level === "ok" ? "level-routine" : "level-prompt"}`}>{v.level === "ok" ? "OK" : "Check"}</span></li>)}</ul>
          </Card>
          {r.comparison_with_paper && (
            <Card title="Comparison with the paper" action={<Provenance kind="reproduced">Paper values</Provenance>}>
              <div className="scroll"><table className="plain wide"><thead><tr><th>Quantity</th><th>Paper</th><th>This run</th><th>Difference</th></tr></thead>
                <tbody>{r.comparison_with_paper.map((c) => <tr key={c.label}><td>{c.label}</td><td>{c.paper}</td><td>{c.reproduced}</td><td className={Math.abs(c.difference) > 0.05 ? "diff-big" : ""}>{c.difference > 0 ? "+" : ""}{c.difference}</td></tr>)}</tbody></table></div>
            </Card>
          )}
          <Card title="Notes"><ul>{r.notes.map((n) => <li key={n}>{n}</li>)}</ul></Card>
        </>
      )}

      {tab === "performance" && (
        <>
          <Card title="Discrimination by cohort (AUC)">
            <GroupedBars label="AUC by cohort and model" domain={[0.4, 1]} keys={models}
              data={[{ name: `${r.dev_site} (CV)`, ...Object.fromEntries(models.map((m) => [m, r.models[m].internal.auc])) },
                ...sites.map((s) => ({ name: s, ...Object.fromEntries(models.map((m) => [m, r.models[m].external[s].auc])) }))]} />
          </Card>
          <Card title="Probability accuracy (Brier score, lower is better)">
            <GroupedBars label="Brier score by cohort and model" keys={models}
              data={[{ name: `${r.dev_site} (CV)`, ...Object.fromEntries(models.map((m) => [m, r.models[m].internal.brier])) },
                ...sites.map((s) => ({ name: s, ...Object.fromEntries(models.map((m) => [m, r.models[m].external[s].brier])) }))]} />
          </Card>
          <Card title="Full metrics">
            <div className="scroll"><table className="plain wide">
              <thead><tr><th>Model</th><th>Cohort</th><th>AUC (95% CI)</th><th>AP</th><th>Sens.</th><th>Spec.</th><th>Prec.</th><th>F1</th><th>Bal. acc.</th><th>Brier</th><th>Cal. int.</th><th>Cal. slope</th></tr></thead>
              <tbody>{models.flatMap((m) => [[`${r.dev_site} (CV)`, r.models[m].internal] as const, ...sites.map((s) => [s, r.models[m].external[s]] as const), ["Pooled external", r.models[m].pooled_external] as const]
                .map(([c, x]) => <tr key={`${m}${c}`}><td>{pretty(m)}</td><td>{c}</td><td>{withCi(x)}</td><td>{fmt(x.average_precision)}</td><td>{fmt(x.sensitivity)}</td><td>{fmt(x.specificity)}</td><td>{fmt(x.precision)}</td><td>{fmt(x.f1)}</td><td>{fmt(x.balanced_accuracy)}</td><td>{fmt(x.brier)}</td><td>{fmt(x.cal_intercept)}</td><td>{fmt(x.cal_slope)}</td></tr>))}</tbody>
            </table></div>
            <p className="muted small">Sensitivity, specificity and precision use a fixed 0.5 threshold. Pooled external AUC mixes cohorts with different prevalence, so the cohort-specific rows are the main evidence.</p>
          </Card>
        </>
      )}
      {tab === "roc" && <Card title={`ROC curves: ${pretty(activeModel)}`}><RocChart curves={selected.roc} /></Card>}
      {tab === "calibration" && (
        <Card title={`Calibration: ${pretty(activeModel)}`}>
          <CalibrationPlot curves={selected.calibration} />
          <table className="plain"><thead><tr><th>Cohort</th><th>Intercept</th><th>Slope</th><th>Brier</th></tr></thead>
            <tbody>{sites.map((s) => <tr key={s}><td>{s}</td><td>{fmt(selected.external[s].cal_intercept)}</td><td>{fmt(selected.external[s].cal_slope)}</td><td>{fmt(selected.external[s].brier)}</td></tr>)}</tbody></table>
          <p className="muted small">Ideal calibration has intercept 0 and slope 1. A positive intercept means the model under-predicts risk in that cohort.</p>
        </Card>
      )}
      {tab === "decision" && (
        <Card title={`Decision curve: ${pretty(activeModel)} on ${siteKey}`} action={<Provenance kind="extension">Additional analysis, not in the paper</Provenance>}>
          <DecisionPlot curve={selected.dca[siteKey]} />
          <p className="muted small">Net benefit compares acting on the model with treating everyone or no one. The prevalence-adjusted line uses the site&apos;s observed prevalence, so it is an upper bound on what a real deployment can know.</p>
        </Card>
      )}
      {tab === "missing" && (
        <>
          <Card title="Missing-data heatmap"><Heatmap rows={cohorts} columns={r.features} values={r.missingness} /></Card>
          <Card title="Feature availability across cohorts">
            <div className="scroll"><table className="plain"><thead><tr><th>Predictor</th><th>Worst-cohort missingness</th><th>Portable</th></tr></thead>
              <tbody>{r.features.map((f) => <tr key={f}><td>{f}</td><td>{r.availability[f].worst_missing_pct}%</td><td>{r.availability[f].portable ? "Yes" : "No"}</td></tr>)}</tbody></table></div>
          </Card>
        </>
      )}
      {tab === "features" && (
        <Card title={`Interpretability: ${pretty(activeModel)}`}>
          <p className="muted">{selected.interpretability.method}</p>
          {selected.interpretability.coefficients && <HorizontalBars label="Coefficients" rows={[...selected.interpretability.coefficients].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 14).map((c) => ({ name: c.term, value: c.value }))} />}
          {selected.interpretability.permutation && <><h4>Permutation importance on pooled external records</h4><Provenance kind="extension">Additional analysis</Provenance><HorizontalBars label="Permutation importance" rows={selected.interpretability.permutation.map((p) => ({ name: p.feature, value: p.value }))} /></>}
          {selected.interpretability.impurity && <><h4>Impurity importance on the development cohort</h4><HorizontalBars label="Impurity importance" rows={selected.interpretability.impurity.map((p) => ({ name: p.feature, value: p.value }))} /></>}
        </Card>
      )}
      {tab === "subgroups" && (
        <Card title={`Subgroup performance${r.subgroup.column ? "" : ""}`} action={<Provenance kind="model">Exploratory</Provenance>}>
          {r.subgroup.rows.length === 0 ? <EmptyState title="No subgroup column was provided" /> : (
            <div className="scroll"><table className="plain wide"><thead><tr><th>Evaluation</th><th>Group</th><th>Records</th><th>With disease</th><th>AUC (95% CI)</th><th>Sensitivity</th><th>Specificity</th></tr></thead>
              <tbody>{r.subgroup.rows.map((s) => <tr key={s.evaluation + s.group}><td>{s.evaluation}</td><td>{s.group}</td><td>{s.n}</td><td>{s.events}</td><td>{fmt(s.auc)}{s.auc_ci ? ` (${fmt(s.auc_ci[0])}–${fmt(s.auc_ci[1])})` : ""}</td><td>{fmt(s.sensitivity)}</td><td>{fmt(s.specificity)}</td></tr>)}</tbody></table></div>
          )}
          <p className="muted small">Model: {pretty(r.subgroup.model)}. Small subgroups give wide intervals; differences here are not evidence of algorithmic bias or its absence.</p>
        </Card>
      )}
      {tab === "recalibration" && (
        <>
          <Notice tone="info" title="Extension analysis">Recalibration experiments come from TransportLab and were not reported in the paper.</Notice>
          {Object.entries(r.recalibration).map(([m, bySite]) => (
            <Card key={m} title={pretty(m)}>
              {Object.entries(bySite).map(([s, v]) => (
                <div key={s} className="tier-result">
                  <h4>{s}</h4>
                  <p>Prevalence-adjusted Brier: {fmt(v.prevalence_adjusted.brier_before, 4)} → {fmt(v.prevalence_adjusted.brier_after, 4)}</p>
                  {Object.keys(v.update_study).length > 0 && (
                    <div className="scroll"><table className="plain"><thead><tr><th>Local cases used</th><th>No update</th><th>Intercept</th><th>Intercept and slope</th></tr></thead>
                      <tbody>{Object.entries(v.update_study).map(([n, b]) => <tr key={n}><td>{n}</td><td>{b.none}</td><td>{b.intercept}</td><td>{b.intercept_slope}</td></tr>)}</tbody></table></div>
                  )}
                  {v.full_update && <p className="muted small">Using all {r.cohorts[s].n} records: intercept shift {v.full_update.intercept.shift}, Brier {v.full_update.brier_before} → {v.full_update.intercept.brier}. {v.full_update.note}</p>}
                </div>
              ))}
            </Card>
          ))}
        </>
      )}
    </div>
  );
}
