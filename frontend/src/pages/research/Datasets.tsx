import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type { Dataset, ModelVersion } from "../../api/types";
import { Card, EmptyState, ErrorState, Field, Notice, Provenance, Spinner, day, when } from "../../components/ui";

export function Datasets() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const list = useQuery({ queryKey: ["datasets"], queryFn: () => api<Dataset[]>("/research/datasets") });
  const upload = useMutation({
    mutationFn: () => { const form = new FormData(); form.append("file", file as File); form.append("name", name); return api<Dataset>("/research/datasets", { method: "POST", form }); },
    onSuccess: (d) => { setWarnings(d.warnings ?? []); setName(""); setFile(null); void queryClient.invalidateQueries({ queryKey: ["datasets"] }); },
    onError: (e) => setError(e instanceof Error ? e.message : "Upload failed."),
  });
  const remove = useMutation({ mutationFn: (id: number) => api(`/research/datasets/${id}`, { method: "DELETE" }), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["datasets"] }) });
  const status = useQuery({ queryKey: ["uci"], queryFn: () => api<{ available: string[]; missing: string[]; note: string }>("/research/uci-status") });
  return (
    <div className="stack">
      <h1>Datasets</h1>
      <Notice tone="info" title="Research data is kept separate">Uploaded datasets are visible only to you and are never mixed with patient records. Files with identifier-like columns (names, emails, phone numbers) are rejected.</Notice>
      <Card title="Upload a dataset">
        <p className="muted">CSV with a header row, 40 to 200,000 rows, up to 200 columns. It needs an outcome column, a site column and predictor columns.</p>
        <div className="grid2">
          <Field id="dn" label="Dataset name"><input id="dn" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field id="df" label="CSV file"><input id="df" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
        </div>
        {error && <Notice tone="warn">{error}</Notice>}
        {warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
        <div className="actions"><button className="btn primary" disabled={!file || name.trim().length < 3 || upload.isPending} onClick={() => { setError(""); setWarnings([]); upload.mutate(); }}>{upload.isPending ? "Validating…" : "Upload and validate"}</button></div>
      </Card>
      <Card title="UCI Heart Disease files on this server">
        {status.data ? <p>{status.data.available.length === 4 ? "All four processed files are present." : `Present: ${status.data.available.join(", ") || "none"}. Missing: ${status.data.missing.join(", ")}.`} <span className="muted">{status.data.note}</span></p> : <Spinner />}
      </Card>
      <Card title="Your datasets">
        {list.isLoading ? <Spinner /> : list.error || !list.data ? <ErrorState error={list.error} /> : list.data.length === 0 ? <EmptyState title="No datasets yet" /> : (
          <ul className="list">
            {list.data.map((d) => (
              <li key={d.id} className="col"><div className="row between"><div><strong>{d.name}</strong><span className="muted small">{d.n_rows.toLocaleString()} rows · {d.columns.length} columns · {day(d.created_at)}</span></div>
                <div className="row"><button className="btn ghost small" onClick={() => setOpen(open === d.id ? null : d.id)}>{open === d.id ? "Hide columns" : "Columns"}</button>
                  <button className="btn ghost small" onClick={() => remove.mutate(d.id)}>Delete</button></div></div>
                {open === d.id && <div className="scroll"><table className="plain"><thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Distinct</th></tr></thead>
                  <tbody>{d.columns.map((c) => <tr key={c.name}><td>{c.name}</td><td>{c.kind}</td><td>{c.missing_pct}%</td><td>{c.n_unique}</td></tr>)}</tbody></table></div>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function ModelRegistry() {
  const { data, error, isLoading } = useQuery({ queryKey: ["registry"], queryFn: () => api<ModelVersion[]>("/research/models") });
  if (isLoading) return <Spinner />;
  if (error || !data) return <ErrorState error={error} />;
  return (
    <div className="stack">
      <h1>Model registry</h1>
      <p className="muted">Deployed inference models. Every assessment stores the version tag that produced it.</p>
      {data.length === 0 ? <EmptyState title="No model registered">Train the model with python -m app.training.</EmptyState> : data.map((m) => (
        <Card key={m.id} title={m.tag} action={m.is_active ? <Provenance kind="reproduced">Active</Provenance> : undefined}>
          <p>Trained {when(m.trained_at)} on <strong>{m.data_source === "uci" ? "the original UCI records" : "synthetic demonstration data"}</strong>.</p>
          {(["core", "clinical"] as const).map((tier) => {
            const t = m.card.deployment[tier];
            return (
              <div key={tier} className="tier-result">
                <h4>{tier === "core" ? "Simple model (7 inputs)" : "Detailed model (10 inputs)"}</h4>
                <p>Held-out-hospital AUC: {Object.entries(t.held_out_site).map(([s, v]) => `${s} ${v.auc ?? "n/a"}`).join(" · ")}</p>
                <p>Second-opinion forest AUC: {Object.entries(t.forest_held_out_site).map(([s, v]) => `${s} ${v.auc ?? "n/a"}`).join(" · ")}</p>
                <p className="muted small">Regularisation C = {t.regularisation_C}. Band cut-offs {t.bands.lower_cut} and {t.bands.higher_cut}. Logistic and forest agree on the band for {t.agreement.same_band_pct}% of held-out records; {t.bootstrap_models} bootstrap models give each score its range.</p>
              </div>
            );
          })}
        </Card>
      ))}
    </div>
  );
}
