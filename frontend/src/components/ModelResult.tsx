import type { ModelEstimate, WellnessResult } from "../api/types";
import { Disclaimer, Notice, Pct } from "./ui";

const bandIcon = { lower: "✓", moderate: "!", higher: "!!" } as const;
const statusText = { good: "On track", watch: "Keep an eye", action: "Needs attention", unknown: "Not provided" } as const;

export function ModelSections({ r }: { r: ModelEstimate }) {
  const o = r.observed;
  return (
    <>
      {r.data_source !== "uci" && (
        <Notice tone="warn" title="Demonstration build">This copy was trained on generated demo data, not the real hospital records. Do not rely on the numbers.</Notice>
      )}
      {r.emergency.active && <Notice tone="danger" title="Get emergency help now">{r.emergency.message}</Notice>}
      <section className={`card band ${r.band}`}>
        <div className="band-head">
          <span className="band-icon" aria-hidden="true">{bandIcon[r.band]}</span>
          <div>
            <p className="eyebrow">Research model band</p>
            <h2>{r.headline}</h2>
          </div>
        </div>
        <p>{r.summary}</p>
        <p><strong>What to do:</strong> {r.action}</p>
        {r.band_raised && r.raised_reason && <p className="raised">Raised for safety: {r.raised_reason}</p>}
      </section>
      <section className="card">
        <h3>How much can you trust this?</h3>
        <p><span className={`chip ${r.confidence.level}`}>Confidence: {r.confidence.level}</span></p>
        {r.confidence.reasons.map((x) => <p key={x} className="muted">{x}</p>)}
        <p>
          In the hospital records behind this model, <strong>{o.n.toLocaleString()}</strong> people landed in this same band.
          About <strong><Pct value={o.rate} /></strong> of them (range <Pct value={o.ci[0]} /> to <Pct value={o.ci[1]} />) were
          found to have significant artery blockage on angiography.
        </p>
        {o.site_min !== null && o.site_max !== null && (
          <p className="muted">
            That share ranged from <Pct value={o.site_min} /> to <Pct value={o.site_max} /> between hospitals, because each hospital
            sends different kinds of patients for testing. Your own chance may differ.
          </p>
        )}
        {r.local && (
          <Notice tone="info" title={`Calibrated to ${r.local.label}`}>
            Using local data{r.local.n ? ` (${r.local.n} patients)` : ""}, the adjusted estimate for people like you there is about <strong>{Math.round(r.local.probability * 100)}%</strong>.
          </Notice>
        )}
        <p className="muted small">
          Model score {r.model_score}/100{r.score_range ? `, plausible range ${r.score_range[0]} to ${r.score_range[1]}` : ""}. It is a ranking score, not a percentage chance.
          The range shows how much the score moves when the model is rebuilt from resampled patients.
        </p>
        {r.second_opinion && (
          <p className={`second-opinion ${r.second_opinion.agrees ? "agree" : "differ"}`}>
            <strong>Second opinion ({r.second_opinion.model}):</strong>{" "}
            {r.second_opinion.agrees ? "places you in the same band." : `places you in the ${r.second_opinion.band} band, so treat this result as less certain.`}
          </p>
        )}
      </section>
      <section className="card">
        <h3>What shaped this estimate</h3>
        <div className="grid2">
          <div>
            <h4>Pushed it up</h4>
            {r.drivers.up.length === 0 && <p className="muted">Nothing notable.</p>}
            <ul className="drivers">{r.drivers.up.map((d) => <li key={d.feature}><span>{d.label}</span><em>{d.effect}</em></li>)}</ul>
          </div>
          <div>
            <h4>Pulled it down</h4>
            {r.drivers.down.length === 0 && <p className="muted">Nothing notable.</p>}
            <ul className="drivers">{r.drivers.down.map((d) => <li key={d.feature}><span>{d.label}</span><em>{d.effect}</em></li>)}</ul>
          </div>
        </div>
        <p className="muted small">Exact linear contributions compared with a typical patient in the reference records. For a linear model these equal SHAP values. They describe patterns in old data and are not causes.</p>
      </section>
      {r.warnings.filter((w) => !w.startsWith("This build")).map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
    </>
  );
}

export function WellnessSections({ r }: { r: WellnessResult }) {
  const tone = r.overall === "good" ? "lower" : r.overall === "some" ? "moderate" : "higher";
  return (
    <>
      {r.urgent.map((u) => <Notice key={u} tone="danger" title="Needs attention today">{u}</Notice>)}
      <section className={`card band ${tone}`}>
        <div className="band-head">
          <span className="band-icon" aria-hidden="true">{tone === "lower" ? "✓" : "!"}</span>
          <div>
            <p className="eyebrow">Risk-factor review</p>
            <h2>{r.headline}</h2>
          </div>
        </div>
        <p>{r.counts.action} needing attention · {r.counts.watch} to keep an eye on · {r.counts.unknown} not provided</p>
        <p className="muted">{r.context}</p>
      </section>
      <section className="card">
        <h3>Your factors</h3>
        <ul className="factors">
          {r.factors.map((f) => (
            <li key={f.key} className={f.status}>
              <div className="factor-head"><strong>{f.label}</strong><span>{f.value}</span><em className={`chip ${f.status}`}>{statusText[f.status]}</em></div>
              <p>{f.detail}</p>
              <p className="tip">{f.tip}</p>
            </li>
          ))}
        </ul>
      </section>
      <section className="card">
        <h3>Next steps</h3>
        <ul>{r.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
      </section>
    </>
  );
}

export function QuickResult({ r, onAgain }: { r: ModelEstimate; onAgain: () => void }) {
  return (
    <div className="result">
      <ModelSections r={r} />
      <section className="card">
        <h3>Take this to your doctor</h3>
        <table className="plain"><tbody>{r.inputs.map((i) => <tr key={i.label}><th>{i.label}</th><td>{i.value}</td></tr>)}</tbody></table>
        <ul>{r.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
      </section>
      <div className="actions no-print">
        <button className="btn primary" onClick={() => window.print()}>Print or save as PDF</button>
        <button className="btn ghost" onClick={onAgain}>Start a new check</button>
      </div>
      <Disclaimer />
    </div>
  );
}

export function QuickWellnessResult({ r, onAgain }: { r: WellnessResult; onAgain: () => void }) {
  return (
    <div className="result">
      <WellnessSections r={r} />
      <div className="actions no-print">
        <button className="btn primary" onClick={() => window.print()}>Print or save as PDF</button>
        <button className="btn ghost" onClick={onAgain}>Start over</button>
      </div>
    </div>
  );
}
