import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { CalibrationChart, GroupedBars, LineChart } from "../charts";
import { experiment, experiments, inspectCsv, paperResults, runDemo, runUpload } from "../platformApi";
import type { CsvInfo, ExperimentRow, Report } from "../platformApi";
import type { PaperRun } from "../types";
import { Field, Notice } from "../ui";

const MODELS: Record<string, string> = { logistic_full: "Logistic, all features", logistic_portable: "Logistic, portable", forest_portable: "Forest, portable" };
const f2 = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : v.toFixed(2));

function Dashboard({ r }: { r: Report }) {
  const sites = Object.keys(r.external.logistic_portable);
  const [site, setSite] = useState(sites[0]);
  const dca = r.dca[site];
  const upd = r.update[site] ?? {};
  const ns = Object.keys(upd);
  const calib = Object.fromEntries(Object.entries(r.calib).map(([k, v]) => [k, { predicted: v.x, observed: v.y }]));
  const features = r.meta.features;
  return (
    <div className="stack">
      <Notice tone={r.provenance.origin === "synthetic_demo" ? "warn" : "info"} title={r.provenance.origin === "synthetic_demo" ? "Synthetic demonstration" : "New experiment"}>{r.provenance.note}</Notice>
      {r.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
      <section className="card stack">
        <h3>Verdict per site (trained on {r.meta.dev_site})</h3>
        {r.verdicts.map((v) => <Notice key={v.site} tone={v.level === "ok" ? "good" : "warn"} title={v.site}>{v.status}</Notice>)}
        <p className="muted small">Portable features: {r.meta.portable.join(", ")}.{r.meta.dropped.length > 0 && ` Excluded for missing data: ${r.meta.dropped.join(", ")}.`}</p>
      </section>
      <section className="card">
        <h3>Discrimination by hospital (AUC)</h3>
        <GroupedBars label="AUC by hospital and model" categories={sites}
          series={Object.keys(MODELS).map((k) => ({ name: MODELS[k], values: sites.map((s) => r.external[k][s].auc) }))} />
        <div className="scroll"><table className="tbl"><thead><tr><th>Hospital</th><th>n</th><th>Prevalence</th><th>AUC (95% CI)</th><th>Brier</th><th>Cal. intercept</th><th>Cal. slope</th><th>Sens.</th><th>Spec.</th></tr></thead>
          <tbody>{sites.map((s) => { const m = r.external.logistic_portable[s]; return (
            <tr key={s}><td>{s}</td><td>{m.n}</td><td>{f2(m.prev)}</td><td>{f2(m.auc)}{m.auc_ci ? ` (${f2(m.auc_ci[0])} to ${f2(m.auc_ci[1])})` : ""}</td><td>{f2(m.brier)}</td><td>{f2(m.cal_intercept)}</td><td>{f2(m.cal_slope)}</td><td>{f2(m.sens)}</td><td>{f2(m.spec)}</td></tr>); })}</tbody></table></div>
      </section>
      <section className="card"><h3>Calibration of the portable logistic model</h3><CalibrationChart curves={calib} label="Calibration curves by hospital" /></section>
      <section className="card stack">
        <div className="row between"><h3>Decision curves and local updating</h3>
          <select aria-label="Hospital" value={site} onChange={(e) => setSite(e.target.value)}>{sites.map((s) => <option key={s}>{s}</option>)}</select></div>
        <p className="muted small">Additional analyses added by this project; they are not results of the original paper.</p>
        <LineChart label="Net benefit by risk threshold" yLabel="Net benefit" x={dca.t.map(String)}
          series={[{ name: "Model", values: dca.raw }, { name: "Prevalence-adjusted", values: dca.adjusted }, { name: "Treat all", values: dca.all, dashed: true }, { name: "Treat none", values: dca.t.map(() => 0), dashed: true }]} />
        {ns.length > 0 ? (
          <LineChart label="Brier score against local labelled cases" yLabel="Brier score" x={ns}
            series={["No update", "Intercept only", "Intercept and slope"].map((name, i) => ({ name, values: ns.map((n) => upd[n][i]) }))} />
        ) : <p className="muted">This site is too small for the update study.</p>}
      </section>
      <section className="card"><h3>Missing data (%)</h3>
        <div className="scroll"><table className="tbl heat"><thead><tr><th />{features.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{Object.entries(r.sites).map(([s, d]) => (
            <tr key={s}><th>{s}</th>{features.map((c) => <td key={c} style={{ background: `rgba(194,65,12,${d.missing[c] / 100})`, color: d.missing[c] > 55 ? "#fff" : undefined }}>{Math.round(d.missing[c])}</td>)}</tr>))}</tbody></table></div>
      </section>
      {Object.keys(r.subgroup).length > 0 && (
        <section className="card"><h3>Subgroups: {r.meta.group_col} (pooled external sites, exploratory)</h3>
          <div className="scroll"><table className="tbl"><thead><tr><th>Group</th><th>n</th><th>AUC</th><th>Sens.</th><th>Spec.</th></tr></thead>
            <tbody>{Object.entries(r.subgroup).map(([g, m]) => <tr key={g}><td>{g}</td><td>{m.n}</td><td>{f2(m.auc)}</td><td>{f2(m.sens)}</td><td>{f2(m.spec)}</td></tr>)}</tbody></table></div></section>
      )}
    </div>
  );
}

function PaperProtocol({ data }: { data: { data_source: string; paper_protocol: Record<string, PaperRun> | null; provenance: string; note: string } }) {
  const real = data.provenance === "reproduced_from_supplied_data";
  const runs = data.paper_protocol ? Object.entries(data.paper_protocol) : [];
  const sites = runs.length ? Object.keys(runs[0][1].external) : [];
  return (
    <section className="card stack">
      <h3>The paper's experiment: Cleveland to external hospitals</h3>
      <Notice tone={real ? "good" : "warn"} title={real ? "Reproduced on the UCI files" : "Synthetic demonstration, not the paper's numbers"}>{data.note}</Notice>
      {runs.length === 0 ? <p className="muted">The model was trained without the paper protocol. Run training without --skip-paper.</p> : (
        <div className="scroll"><table className="tbl"><thead><tr><th>Model</th><th>Cleveland CV AUC</th>{sites.map((s) => <th key={s}>{s}</th>)}<th>Pooled external</th></tr></thead>
          <tbody>{runs.map(([k, run]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{f2(run.internal.auc)}</td>{sites.map((s) => <td key={s}>{f2(run.external[s].auc)}</td>)}<td>{f2(run.pooled_external.auc)}</td></tr>)}</tbody></table></div>
      )}
    </section>
  );
}

function Upload({ onDone }: { onDone: (e: ExperimentRow) => void }) {
  const [info, setInfo] = useState<CsvInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [v, setV] = useState({ name: "", target: "", site_col: "", dev_site: "", group_col: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pick = async (e: ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0];
    if (!chosen) return;
    setFile(chosen);
    setError("");
    try {
      const out = await inspectCsv(chosen);
      const grouped = out.columns.filter((c) => c.values);
      setInfo(out);
      setV({ name: chosen.name, target: out.columns[0].name, site_col: grouped[0]?.name ?? "", dev_site: grouped[0]?.values?.[0] ?? "", group_col: "" });
    } catch (err) {
      setInfo(null);
      setError((err as Error).message);
    }
  };
  const sites = info?.columns.find((c) => c.name === v.site_col)?.values ?? [];
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    Object.entries(v).forEach(([k, val]) => form.append(k, val));
    setBusy(true);
    setError("");
    try {
      onDone(await runUpload(form));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const select = (k: keyof typeof v, names: string[], blank = false) => (
    <select id={k} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value, ...(k === "site_col" ? { dev_site: info?.columns.find((c) => c.name === e.target.value)?.values?.[0] ?? "" } : {}) })}>
      {blank && <option value="">None</option>}{names.map((n) => <option key={n}>{n}</option>)}
    </select>
  );
  return (
    <form className="card stack" onSubmit={submit}>
      <h3>Run your own cross-site experiment</h3>
      <p className="muted">Upload a CSV with an outcome column (0 = no, above 0 = yes) and a site column. Rows are never stored, only the aggregate results.</p>
      {error && <Notice tone="danger">{error}</Notice>}
      <Field id="csv" label="CSV file (up to 10 MB)"><input id="csv" type="file" accept=".csv" onChange={pick} /></Field>
      {info && (
        <>
          <p className="muted small">{info.rows} rows read.</p>
          <Field id="name" label="Experiment name"><input id="name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} maxLength={120} required /></Field>
          <div className="grid2">
            <Field id="target" label="Outcome column">{select("target", info.columns.map((c) => c.name))}</Field>
            <Field id="site_col" label="Site column">{select("site_col", info.columns.filter((c) => c.values).map((c) => c.name))}</Field>
            <Field id="dev_site" label="Development site">{select("dev_site", sites)}</Field>
            <Field id="group_col" label="Subgroup column (optional)">{select("group_col", info.columns.filter((c) => c.values).map((c) => c.name), true)}</Field>
          </div>
          <button className="btn primary" disabled={busy}>{busy ? "Running, this can take a minute..." : "Run experiment"}</button>
        </>
      )}
    </form>
  );
}

export default function Research() {
  const [list, setList] = useState<ExperimentRow[]>([]);
  const [report, setReport] = useState<{ name: string; result: Report } | null>(null);
  const [paper, setPaper] = useState<Parameters<typeof PaperProtocol>[0]["data"] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => experiments().then(setList).catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
    paperResults().then(setPaper).catch((e: Error) => setError(e.message));
  }, []);
  const open = (id: number) => experiment(id).then(setReport).catch((e: Error) => setError(e.message));
  const done = (e: ExperimentRow) => { load(); open(e.id); };
  const demo = async () => {
    setBusy(true);
    try { done(await runDemo()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <section className="card stack">
        <h2>Research workspace</h2>
        <p className="muted">Cross-hospital validation, calibration, decision curves, missing data and subgroups. Results are labelled as reproduced from the paper, new experiments or synthetic demonstrations.</p>
        {error && <Notice tone="danger">{error}</Notice>}
        <div className="row between">
          <button className="btn ghost" onClick={demo} disabled={busy}>{busy ? "Running demo..." : "Run synthetic demo"}</button>
        </div>
        <ul className="history">{list.map((e) => (
          <li key={e.id}><button className="linklike" onClick={() => open(e.id)}><strong>{e.name}</strong><span>{e.origin === "synthetic_demo" ? "Synthetic demonstration" : "Uploaded dataset"}</span><time dateTime={e.created_at}>{new Date(e.created_at).toLocaleString()}</time></button></li>))}</ul>
      </section>
      {paper && <PaperProtocol data={paper} />}
      <Upload onDone={done} />
      {report && <><h2>{report.name}</h2><Dashboard r={report.result} /></>}
    </div>
  );
}
