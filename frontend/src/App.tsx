import { useState } from "react";
import { addHistory, loadHistory } from "./storage";
import Account from "./pages/Account";
import Patients from "./pages/Patients";
import Record from "./pages/Record";
import Research from "./pages/Research";
import { getSession, setSession } from "./session";
import type { Role, Session } from "./session";
import Check from "./pages/Check";
import Clinic from "./pages/Clinic";
import Evidence from "./pages/Evidence";
import History from "./pages/History";
import Home from "./pages/Home";
import { CheckResult, WellnessView } from "./pages/Result";
import Wellness from "./pages/Wellness";
import { useRoute } from "./router";
import type { AssessmentResult, HistoryEntry, WellnessResult } from "./types";
import { Disclaimer, Notice } from "./ui";

const base = [
  { path: "/", label: "Home" },
  { path: "/history", label: "History" },
  { path: "/evidence", label: "How it works" },
  { path: "/clinic", label: "For clinics" },
];

const roleNav: Record<Role, { path: string; label: string }> = {
  patient: { path: "/record", label: "My record" },
  clinician: { path: "/patients", label: "Patients" },
  admin: { path: "/patients", label: "Patients" },
  researcher: { path: "/research", label: "Research" },
};

const newId = () => Math.random().toString(36).slice(2, 10);

export default function App() {
  const [path, go] = useRoute();
  const [session, setSessionState] = useState<Session | null>(getSession());
  const [shown, setShown] = useState<HistoryEntry | null>(() => loadHistory()[0] ?? null);

  const finishCheck = (r: AssessmentResult) => {
    const entry: HistoryEntry = {
      id: newId(), createdAt: new Date().toISOString(), kind: "check", title: r.headline,
      subtitle: `Symptom check · ${r.inputs[0].value}, ${r.inputs[1].value.toLowerCase()}`, check: r,
    };
    addHistory(entry);
    setShown(entry);
    go("/result");
  };

  const finishWellness = (r: WellnessResult, subtitle: string) => {
    const entry: HistoryEntry = {
      id: newId(), createdAt: new Date().toISOString(), kind: "wellness", title: r.headline,
      subtitle: `Risk factors · ${subtitle}`, wellness: r,
    };
    addHistory(entry);
    setShown(entry);
    go("/result");
  };

  const open = (e: HistoryEntry) => {
    setShown(e);
    go("/result");
  };

  const signIn = (s: Session) => {
    setSessionState(s);
    go(roleNav[s.role].path);
  };
  const signOut = () => {
    setSession(null);
    setSessionState(null);
    go("/");
  };
  const nav = session ? [...base, roleNav[session.role]] : base;
  const gate = (roles: Role[], element: JSX.Element) =>
    !session ? <Account onDone={signIn} /> : roles.includes(session.role) ? element : <Notice tone="warn" title="Not available">Your account role cannot open this page.</Notice>;

  let page;
  if (path === "/check/symptomatic") page = <Check key="s" pathway="symptomatic" onResult={finishCheck} />;
  else if (path === "/check/referred") page = <Check key="r" pathway="referred" onResult={finishCheck} />;
  else if (path === "/wellness") page = <Wellness onResult={finishWellness} />;
  else if (path === "/result" && shown?.check) page = <CheckResult r={shown.check} onAgain={() => go("/")} />;
  else if (path === "/result" && shown?.wellness) page = <WellnessView r={shown.wellness} onAgain={() => go("/")} />;
  else if (path === "/history") page = <History onOpen={open} />;
  else if (path === "/evidence") page = <Evidence />;
  else if (path === "/clinic") page = <Clinic />;
  else if (path === "/account") page = <Account onDone={signIn} />;
  else if (path === "/record") page = gate(["patient"], <Record />);
  else if (path === "/patients") page = gate(["clinician", "admin"], <Patients canReview={session?.role === "clinician"} />);
  else if (path === "/research") page = gate(["researcher"], <Research />);
  else page = <Home go={go} />;

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top no-print">
        <button className="brand" onClick={() => go("/")} aria-label="CardioLens home"><span aria-hidden="true">🫀</span> CardioLens</button>
        <nav aria-label="Main">
          {nav.map((n) => (
            <button key={n.path} className={path === n.path ? "active" : ""} onClick={() => go(n.path)} aria-current={path === n.path ? "page" : undefined}>{n.label}</button>
          ))}
          {session
            ? <button onClick={signOut}>Sign out ({session.name})</button>
            : <button className={path === "/account" ? "active" : ""} onClick={() => go("/account")}>Sign in</button>}
        </nav>
      </header>
      <main id="main" className={["/research", "/patients"].includes(path) ? "wide" : undefined}>{page}</main>
      <footer className="no-print"><Disclaimer /></footer>
    </>
  );
}
