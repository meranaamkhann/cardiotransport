import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { Experiment, Metrics } from "../../api/types";
import { GroupedBars } from "../../components/charts";
import { Card, EmptyState, ErrorState, Field, Notice, Spinner } from "../../components/ui";
import { provenanceBadge } from "./Experiments";

const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : v.toFixed(3));
const delta = (a: number | null | undefined, b: number | null | undefined) =>
  a === null || a === undefined || b === null || b === undefined ? "n/a" : `${b - a >= 0 ? "+" : ""}${(b - a).toFixed(3)}`;

const METRICS: { key: keyof Metrics; label: string }[] = [
  { key: "auc", label: "AUC" }, { key: "brier", label: "Brier" }, { key: "cal_intercept", label: "Cal. intercept" }, { key: "cal_slope", label: "Cal. slope" },
];

export default function Compare() {
  const list = useQuery({ queryKey: ["experiments"], queryFn: () => api<Experiment[]>("/research/experiments") });
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [model, setModel] = useState("portable_logistic");
  const done = (list.data ?? []).filter((e) => e.status === "completed");
  const details = useQueries({
    queries: [first, second].map((id) => ({ queryKey: ["experiment", id], queryFn: () => api<Experiment>(`/research/experiments/${id}`), enabled: Boolean(id) })),
  });
  if (list.isLoading) return <Spinner />;
  if (list.error) return <ErrorState error={list.error} />;
  const [a, b] = [details[0].data, details[1].data];
  const ra = a?.result, rb = b?.result;
  const modelNames = ra && rb ? Object.keys(ra.models).filter((m) => m in rb.models) : [];
  const chosen = modelNames.includes(model) ? model : modelNames[0];
  const sites = ra && rb ? ra.sites_external.filter((s) => rb.sites_external.includes(s)) : [];

  return (
    <div className="stack">
      <div><h1>Compare runs</h1><p className="muted">Put two completed experiments side by side. A useful pair: the paper protocol with and without recoding of zero cholesterol values.</p></div>
      {done.length < 2 ? <EmptyState title="You need two completed experiments">Run the paper protocol twice, once with zero-value recoding switched on, then come back here.</EmptyState> : (
        <Card>
          <div className="grid2">
            <Field id="ca" label="Run A (baseline)"><select id="ca" value={first} onChange={(e) => setFirst(e.target.value)}><option value="">Select</option>{done.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>
            <Field id="cb" label="Run B"><select id="cb" value={second} onChange={(e) => setSecond(e.target.value)}><option value="">Select</option>{done.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field>
          </div>
        </Card>
      )}
      {ra && rb && a && b && (
        <>
          <Card title="What differs between the runs">
            <table className="plain"><thead><tr><th /><th>Run A</th><th>Run B</th></tr></thead><tbody>
              <tr><th>Type</th><td>{provenanceBadge(a.provenance)}</td><td>{provenanceBadge(b.provenance)}</td></tr>
              <tr><th>Data</th><td>{ra.meta.data_source}</td><td>{rb.meta.data_source}</td></tr>
              <tr><th>Zero cholesterol / BP</th><td>{ra.meta.recode_zeros ? "recoded as missing" : "kept as recorded"}</td><td>{rb.meta.recode_zeros ? "recoded as missing" : "kept as recorded"}</td></tr>
              <tr><th>Bootstrap resamples</th><td>{ra.meta.bootstrap}</td><td>{rb.meta.bootstrap}</td></tr>
            </tbody></table>
            {ra.meta.data_source !== rb.meta.data_source && <Notice tone="warn">The runs use different data sources, so differences may not be comparable.</Notice>}
          </Card>
          {chosen && (
            <Card title="Metric differences" action={<select aria-label="Model" value={chosen} onChange={(e) => setModel(e.target.value)}>{modelNames.map((m) => <option key={m} value={m}>{m.replace(/_/g, " ")}</option>)}</select>}>
              <GroupedBars label="AUC in run A and run B" domain={[0.4, 1]} keys={["Run A", "Run B"]}
                data={sites.map((s) => ({ name: s, "Run A": ra.models[chosen].external[s].auc, "Run B": rb.models[chosen].external[s].auc }))} />
              <div className="scroll"><table className="plain wide">
                <thead><tr><th>Cohort</th>{METRICS.map((m) => <th key={m.key}>{m.label} (A, B, change)</th>)}</tr></thead>
                <tbody>{sites.map((s) => (
                  <tr key={s}><td>{s}</td>{METRICS.map((m) => {
                    const x = ra.models[chosen].external[s][m.key] as number | null, y = rb.models[chosen].external[s][m.key] as number | null;
                    return <td key={m.key}>{fmt(x)}, {fmt(y)}, <strong>{delta(x, y)}</strong></td>;
                  })}</tr>))}
                </tbody></table></div>
              <p className="muted small">For the calibration intercept, a value closer to 0 means better baseline calibration. For the slope, closer to 1 is better.</p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
