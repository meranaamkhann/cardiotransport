import type { ReactNode } from "react";
import type { Level } from "../api/types";

export function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {hint && <p className="hint" id={`${id}-hint`}>{hint}</p>}
      {children}
    </div>
  );
}

export function NumberInput({ id, value, onChange, unit, min, max, step }: {
  id: string; value: string; onChange: (v: string) => void; unit?: string; min?: number; max?: number; step?: number;
}) {
  return (
    <div className="input-unit">
      <input id={id} type="number" inputMode="decimal" value={value} min={min} max={max} step={step ?? "any"}
        aria-describedby={`${id}-hint`} onChange={(e) => onChange(e.target.value)} />
      {unit && <span>{unit}</span>}
    </div>
  );
}

export function Choices<T extends string>({ name, value, options, onChange }: {
  name: string; value: T | ""; options: { value: T; title: string; text?: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="choices" role="radiogroup" aria-label={name}>
      {options.map((o) => (
        <label key={o.value} className={`choice ${value === o.value ? "on" : ""}`}>
          <input type="radio" name={name} checked={value === o.value} onChange={() => onChange(o.value)} />
          <span className="choice-title">{o.title}</span>
          {o.text && <span className="choice-text">{o.text}</span>}
        </label>
      ))}
    </div>
  );
}

export function Notice({ tone, title, children }: { tone: "info" | "warn" | "danger" | "good"; title?: string; children: ReactNode }) {
  const icon = { info: "i", warn: "!", danger: "!", good: "✓" }[tone];
  return (
    <div className={`notice ${tone}`} role={tone === "danger" ? "alert" : undefined}>
      <span className="notice-icon" aria-hidden="true">{icon}</span>
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function Pct({ value }: { value: number | null | undefined }) {
  return <>{value === null || value === undefined ? "n/a" : `${Math.round(value * 100)}%`}</>;
}

export function Disclaimer() {
  return (
    <p className="disclaimer">
      CardioLens is an educational research prototype built on 1980s hospital records. It cannot diagnose heart disease
      and does not replace a doctor. In an emergency, call your local emergency number.
    </p>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <Notice tone="warn" title="We could not load this">
      {message}
      {retry && <div className="actions"><button className="btn ghost small" onClick={retry}>Try again</button></div>}
    </Notice>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  );
}

export function Card({ title, action, children, className = "" }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          {title && <h2>{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, status }: { label: string; value: ReactNode; hint?: string; status?: { tone: "good" | "watch" | "action" | "unknown"; label: string } }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
      {status && status.tone !== "unknown" && <StatusChip tone={status.tone} label={status.label} />}
    </div>
  );
}

const levelText: Record<Level, string> = {
  routine: "Routine", soon: "See a doctor soon", prompt: "Within days", urgent: "Same day", emergency: "Emergency",
};

export function LevelBadge({ level }: { level: Level }) {
  return <span className={`badge level-${level}`}>{levelText[level]}</span>;
}

export function Provenance({ kind, children }: { kind: "reported" | "model" | "clinician" | "extension" | "synthetic" | "reproduced" | "new"; children: ReactNode }) {
  return <span className={`prov prov-${kind}`}>{children}</span>;
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} className={value === t.id ? "active" : ""} onClick={() => onChange(t.id)}>{t.label}</button>
      ))}
    </div>
  );
}

export const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });

export function Skeleton({ lines = 3, height = 18 }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => <span key={i} style={{ height, width: `${100 - i * 12}%` }} />)}
    </div>
  );
}

export function StatusChip({ tone, label }: { tone: "good" | "watch" | "action" | "unknown"; label: string }) {
  return <em className={`chip ${tone}`}>{label}</em>;
}
