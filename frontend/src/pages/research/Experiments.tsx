import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Dataset, Experiment } from "../../api/types";
import { Card, EmptyState, ErrorState, Field, Notice, Provenance, Spinner, when } from "../../components/ui";

export const provenanceBadge = (p: Experiment["provenance"]) =>
  p === "reproduced" ? <Provenance kind="reproduced">Reproduced from the paper</Provenance>
    : p === "synthetic_demo" ? <Provenance kind="synthetic">Synthetic demonstration</Provenance>
      : <Provenance kind="new">New experiment</Provenance>;

export default function Experiments() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"paper_replication" | "custom_validation">("paper_replication");
  const [f, setF] = useState({ name: "", source: "uci", recode: false, bootstrap: "1000", repeats: "10", dataset: "", target: "", site: "", dev: "", features: [] as string[], group: "", maxMissing: "30" });
  const [error, setError] = useState("");
  const list = useQuery({
    queryKey: ["experiments"], queryFn: () => api<Experiment[]>("/research/experiments"),
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === "queued" || e.status === "running") ? 2500 : false),
  });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => api<Dataset[]>("/research/datasets") });
  const chosen = datasets.data?.find((d) => String(d.id) === f.dataset);
  const create = useMutation({
    mutationFn: () => api<Experiment>("/research/experiments", { method: "POST", body: kind === "paper_replication"
      ? { name: f.name, kind, source: f.source, recode_zeros: f.recode, bootstrap: Number(f.bootstrap), repeats: Number(f.repeats) }
      : { name: f.name, kind, dataset_id: Number(f.dataset), target_column: f.target, site_column: f.site, dev_site: f.dev, feature_columns: f.features,
          group_column: f.group || null, bootstrap: Number(f.bootstrap), repeats: Math.min(Number(f.repeats), 10), max_missing: Number(f.maxMissing) / 100 } }),
    onSuccess: (e) => { void queryClient.invalidateQueries({ queryKey: ["experiments"] }); setOpen(false); navigate(`/research/experiments/${e.id}`); },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not start."),
  });
  const toggleFeature = (name: string) => setF((s) => ({ ...s, features: s.features.includes(name) ? s.features.filter((x) => x !== name) : [...s.features, name] }));

  return (
    <div className="stack">
      <div className="row between"><div><h1>Experiments</h1><p className="muted">Cross-hospital validation runs. Every result carries its provenance.</p></div>
        <button className="btn primary" onClick={() => setOpen(!open)}>{open ? "Close" : "New experiment"}</button></div>
      {open && (
        <Card title="New experiment">
          <Field id="en" label="Name"><input id="en" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <div className="choices" role="radiogroup" aria-label="Experiment type">
            <label className={`choice ${kind === "paper_replication" ? "on" : ""}`}><input type="radio" checked={kind === "paper_replication"} onChange={() => setKind("paper_replication")} /><span className="choice-title">Paper protocol</span><span className="choice-text">Train on Cleveland, evaluate on Hungary, Switzerland and Long Beach VA with the four paper models.</span></label>
            <label className={`choice ${kind === "custom_validation" ? "on" : ""}`}><input type="radio" checked={kind === "custom_validation"} onChange={() => setKind("custom_validation")} /><span className="choice-title">Your own multi-site dataset</span><span className="choice-text">Choose columns from an uploaded dataset and validate across its sites.</span></label>
          </div>
          {kind === "paper_replication" ? (
            <>
              <div className="grid2">
                <Field id="src" label="Data source"><select id="src" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}><option value="uci">UCI Heart Disease (original records)</option><option value="synthetic">Synthetic demonstration data</option></select></Field>
                <Field id="boot" label="Bootstrap resamples (paper: 2000)"><input id="boot" type="number" min={100} max={2000} value={f.bootstrap} onChange={(e) => setF({ ...f, bootstrap: e.target.value })} /></Field>
                <Field id="rep" label="CV repeats (paper: 10)"><input id="rep" type="number" min={1} max={10} value={f.repeats} onChange={(e) => setF({ ...f, repeats: e.target.value })} /></Field>
              </div>
              <label className="check"><input type="checkbox" checked={f.recode} onChange={(e) => setF({ ...f, recode: e.target.checked })} /><span>Recode zero cholesterol and blood pressure as missing. The paper did not do this, so the run is labelled a new experiment instead of a reproduction.</span></label>
            </>
          ) : (
            <>
              <div className="grid2">
                <Field id="ds" label="Dataset"><select id="ds" value={f.dataset} onChange={(e) => setF({ ...f, dataset: e.target.value, target: "", site: "", features: [] })}><option value="">Select</option>{datasets.data?.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.n_rows} rows)</option>)}</select></Field>
                {chosen && <>
                  <Field id="tg" label="Outcome column (above 0 counts as disease)"><select id="tg" value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })}><option value="">Select</option>{chosen.columns.filter((c) => c.kind === "numeric").map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
                  <Field id="st" label="Site column"><select id="st" value={f.site} onChange={(e) => setF({ ...f, site: e.target.value })}><option value="">Select</option>{chosen.columns.map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
                  <Field id="dv" label="Development site (value in the site column)"><input id="dv" value={f.dev} onChange={(e) => setF({ ...f, dev: e.target.value })} /></Field>
                  <Field id="gp" label="Subgroup column (optional)"><select id="gp" value={f.group} onChange={(e) => setF({ ...f, group: e.target.value })}><option value="">None</option>{chosen.columns.map((c) => <option key={c.name}>{c.name}</option>)}</select></Field>
                  <Field id="bt" label="Bootstrap resamples"><input id="bt" type="number" min={100} max={2000} value={f.bootstrap} onChange={(e) => setF({ ...f, bootstrap: e.target.value })} /></Field>
                  <Field id="mm" label="Portable if missing at most (%)"><input id="mm" type="number" min={5} max={90} value={f.maxMissing} onChange={(e) => setF({ ...f, maxMissing: e.target.value })} /></Field>
                </>}
              </div>
              {chosen && (
                <Field id="feats" label="Predictor columns">
                  <div className="checks cols">{chosen.columns.filter((c) => c.name !== f.target && c.name !== f.site).map((c) => (
                    <label key={c.name} className="check"><input type="checkbox" checked={f.features.includes(c.name)} onChange={() => toggleFeature(c.name)} /><span>{c.name} <span className="muted small">{c.kind}, {c.missing_pct}% missing</span></span></label>))}</div>
                </Field>
              )}
            </>
          )}
          {error && <Notice tone="warn">{error}</Notice>}
          <div className="actions"><button className="btn primary" disabled={create.isPending || f.name.trim().length < 3} onClick={() => { setError(""); create.mutate(); }}>{create.isPending ? "Starting…" : "Run experiment"}</button></div>
        </Card>
      )}
      {list.isLoading ? <Spinner /> : list.error || !list.data ? <ErrorState error={list.error} /> : list.data.length === 0 ? (
        <EmptyState title="No experiments yet">Run the paper protocol on synthetic data to see the dashboard, or on the original UCI records if the server can reach them.</EmptyState>
      ) : (
        <div className="card scroll">
          <table className="plain wide">
            <thead><tr><th>Experiment</th><th>Provenance</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              {list.data.map((e) => (
                <tr key={e.id}><td><Link to={`/research/experiments/${e.id}`}>{e.name}</Link></td><td>{provenanceBadge(e.provenance)}</td>
                  <td>{e.status === "running" || e.status === "queued" ? <span><progress max={1} value={e.progress} /> {e.stage}</span> : <span className={`badge status-${e.status}`}>{e.status}</span>}</td><td>{when(e.created_at)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
