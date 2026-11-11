import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { Disclaimer } from "./ui";

const menus: Record<Role, { to: string; label: string; end?: boolean }[]> = {
  patient: [
    { to: "/app", label: "Overview", end: true }, { to: "/app/symptoms", label: "Symptom assessment" },
    { to: "/app/wellness", label: "Wellness assessment" }, { to: "/app/measurements", label: "Measurements" },
    { to: "/app/assessments", label: "History" }, { to: "/app/appointments", label: "Appointments" },
    { to: "/app/profile", label: "Profile and privacy" },
  ],
  clinician: [
    { to: "/clinic", label: "Review queue", end: true }, { to: "/clinic/patients", label: "Patients" },
    { to: "/clinic/calibration", label: "Local calibration" },
  ],
  clinic_admin: [
    { to: "/clinic/team", label: "Team and audit" }, { to: "/clinic/calibration", label: "Local calibration" },
  ],
  researcher: [
    { to: "/research", label: "Experiments", end: true }, { to: "/research/datasets", label: "Datasets" }, { to: "/research/compare", label: "Compare runs" },
    { to: "/research/models", label: "Model registry" },
  ],
};

function readSize(): "normal" | "large" {
  try {
    return window.localStorage.getItem("cardiolens.size") === "large" ? "large" : "normal";
  } catch {
    return "normal";
  }
}

export function TextSizeToggle() {
  const [size, setSize] = useState(readSize);
  useEffect(() => {
    document.documentElement.dataset.size = size;
    try {
      window.localStorage.setItem("cardiolens.size", size);
    } catch {
      return;
    }
  }, [size]);
  return (
    <button className="btn ghost small" aria-pressed={size === "large"} onClick={() => setSize(size === "large" ? "normal" : "large")}>
      {size === "large" ? "Normal text" : "Larger text"}
    </button>
  );
}

const roleName: Record<Role, string> = { patient: "Patient", clinician: "Clinician", clinic_admin: "Clinic administrator", researcher: "Researcher" };

export function PublicLayout() {
  const { user } = useAuth();
  return (
    <div className="public">
      <header className="site-header">
        <Link to="/" className="brand"><span aria-hidden="true">🫀</span> CardioLens</Link>
        <nav aria-label="Main">
          <NavLink to="/how-it-works">How it works</NavLink>
          <NavLink to="/quick-check">Quick check</NavLink>
          <TextSizeToggle />
          {user ? <Link className="btn primary small" to={homeFor(user.role)}>Open workspace</Link>
            : <><NavLink to="/login">Sign in</NavLink><Link className="btn primary small" to="/register">Create account</Link></>}
        </nav>
      </header>
      <main id="main" className="public-main"><Outlet /></main>
      <footer className="site-footer"><Disclaimer /></footer>
    </div>
  );
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand"><span aria-hidden="true">🫀</span> CardioLens</Link>
        <p className="role-chip">{roleName[user.role]}</p>
        <nav aria-label="Workspace">
          {menus[user.role].map((m) => <NavLink key={m.to} to={m.to} end={m.end}>{m.label}</NavLink>)}
        </nav>
        <div className="sidebar-foot">
          <strong>{user.full_name}</strong>
          <span className="muted small">{user.clinic?.name ?? user.email}</span>
          <TextSizeToggle />
          <button className="btn ghost small" onClick={() => { signOut(); navigate("/"); }}>Sign out</button>
        </div>
      </aside>
      <div className="shell-main">
        <main id="main" className="content"><Outlet /></main>
        <Disclaimer />
      </div>
    </div>
  );
}
