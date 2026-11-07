import type { ReactNode } from "react";

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
