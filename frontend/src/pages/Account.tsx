import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { login, register } from "../platformApi";
import { setSession } from "../session";
import type { Session } from "../session";
import { Field, Notice } from "../ui";

export default function Account({ onDone }: { onDone: (s: Session) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ name: "", email: "", password: "", clinic: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const out = mode === "login"
        ? await login(f.email, f.password)
        : await register({ name: f.name, email: f.email, password: f.password, clinic: f.clinic || undefined });
      const session = { token: out.access_token, role: out.role, name: out.name };
      setSession(session);
      onDone(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{mode === "login" ? "Sign in" : "Create a patient account"}</h2>
      <p className="muted">Signed-in patients keep their assessments in their account. Clinicians and researchers are added by a clinic administrator.</p>
      {error && <Notice tone="danger">{error}</Notice>}
      {mode === "register" && <Field id="name" label="Your name"><input id="name" value={f.name} onChange={set("name")} required maxLength={80} /></Field>}
      <Field id="email" label="Email"><input id="email" type="email" value={f.email} onChange={set("email")} required autoComplete="email" /></Field>
      <Field id="password" label="Password" hint={mode === "register" ? "At least 10 characters." : undefined}>
        <input id="password" type="password" value={f.password} onChange={set("password")} required minLength={mode === "register" ? 10 : 1} autoComplete={mode === "login" ? "current-password" : "new-password"} />
      </Field>
      {mode === "register" && (
        <Field id="clinic" label="Clinic code (optional)" hint="Lets your clinic's clinicians review your assessments.">
          <input id="clinic" value={f.clinic} onChange={set("clinic")} maxLength={60} />
        </Field>
      )}
      <div className="row between">
        <button className="btn primary" disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="btn ghost" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "New here? Register" : "Have an account? Sign in"}
        </button>
      </div>
    </form>
  );
}
