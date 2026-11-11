import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { homeFor, useAuth } from "../../auth/AuthContext";
import { Field, Notice } from "../../components/ui";

export function Login() {
  const { user, signIn } = useAuth();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setBusy(false);
    }
  };

  if (user) return <Navigate to={from ?? homeFor(user.role)} replace />;

  return (
    <form className="card auth" onSubmit={submit} noValidate>
      <h1>Sign in</h1>
      <Field id="email" label="Email"><input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
      <Field id="password" label="Password"><input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
      {error && <Notice tone="warn">{error}</Notice>}
      <div className="actions"><button className="btn primary" disabled={busy || !email || !password}>{busy ? "Signing in…" : "Sign in"}</button></div>
      <p className="muted">New here? <Link to="/register">Create an account</Link> or <Link to="/register-clinic">register a clinic</Link>.</p>
    </form>
  );
}

export function Register({ clinic = false }: { clinic?: boolean }) {
  const { user, register } = useAuth();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", clinic_code: "", clinic_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (form.password.length < 10) return setError("Use at least 10 characters, including a letter and a digit.");
    setError("");
    setBusy(true);
    try {
      const body = clinic
        ? { clinic_name: form.clinic_name, email: form.email, password: form.password, full_name: form.full_name }
        : { email: form.email, password: form.password, full_name: form.full_name, clinic_code: form.clinic_code || null };
      await register(body, clinic);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not register.");
      setBusy(false);
    }
  };

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  return (
    <form className="card auth" onSubmit={submit} noValidate>
      <h1>{clinic ? "Register a clinic" : "Create your account"}</h1>
      {clinic && <Field id="clinic_name" label="Clinic name"><input id="clinic_name" value={form.clinic_name} onChange={(e) => set("clinic_name", e.target.value)} required /></Field>}
      <Field id="full_name" label="Full name"><input id="full_name" autoComplete="name" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required /></Field>
      <Field id="email" label="Email"><input id="email" type="email" autoComplete="username" value={form.email} onChange={(e) => set("email", e.target.value)} required /></Field>
      <Field id="password" label="Password" hint="At least 10 characters with a letter and a digit."><input id="password" type="password" autoComplete="new-password" value={form.password} onChange={(e) => set("password", e.target.value)} required /></Field>
      {!clinic && <Field id="clinic_code" label="Clinic code (optional)" hint="Enter it only if you want that clinic to see your records. You can leave at any time."><input id="clinic_code" value={form.clinic_code} maxLength={16} onChange={(e) => set("clinic_code", e.target.value)} /></Field>}
      {error && <Notice tone="warn">{error}</Notice>}
      <div className="actions"><button className="btn primary" disabled={busy}>{busy ? "Creating…" : clinic ? "Register clinic" : "Create account"}</button></div>
      <p className="muted">Already registered? <Link to="/login">Sign in</Link>.</p>
    </form>
  );
}
