import { lazy, Suspense, useEffect, useRef } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import RequireRole from "./auth/Guard";
import { AppShell, PublicLayout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { CalibrationPage, PatientDirectory, PatientPage, ReviewQueue, TeamPage } from "./pages/clinic/Workspace";
import Dashboard from "./pages/patient/Dashboard";
import { SymptomAssessment, WellnessAssessment } from "./pages/patient/Assess";
import { Appointments, AssessmentDetail, Assessments, Measurements, ProfilePage } from "./pages/patient/Records";
import { Login, Register } from "./pages/public/AuthPages";
import Landing from "./pages/public/Landing";
import { QuickRun } from "./pages/public/QuickStart";
import Experiments from "./pages/research/Experiments";
import { useAuth } from "./auth/AuthContext";

const HowItWorks = lazy(() => import("./pages/public/HowItWorks"));
const Compare = lazy(() => import("./pages/research/Compare"));
const ExperimentDashboard = lazy(() => import("./pages/research/Dashboard"));
const Datasets = lazy(() => import("./pages/research/Datasets").then((m) => ({ default: m.Datasets })));
const ModelRegistry = lazy(() => import("./pages/research/Datasets").then((m) => ({ default: m.ModelRegistry })));

function Missing() {
  return <div className="card"><h1>Page not found</h1><p className="muted">The page you are looking for does not exist.</p></div>;
}

function ClinicHome() {
  const { user } = useAuth();
  return user?.role === "clinic_admin" ? <TeamPage /> : <ReviewQueue />;
}

function RouteEffects() {
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    const announce = first.current;
    first.current = false;
    const timer = window.setTimeout(() => {
      const heading = document.querySelector("main h1");
      document.title = heading?.textContent ? `${heading.textContent} · CardioLens` : "CardioLens";
      const active = document.activeElement;
      const typing = active instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      const main = document.getElementById("main");
      if (!announce && main && !typing) {
        main.setAttribute("tabindex", "-1");
        main.focus({ preventScroll: true });
      }
    }, 60);
    return () => window.clearTimeout(timer);
  }, [pathname]);
  return null;
}

export default function App() {
  const { loading } = useAuth();
  if (loading) return <Spinner label="Starting CardioLens" />;
  return (
    <Suspense fallback={<Spinner />}>
    <RouteEffects />
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="how-it-works" element={<HowItWorks />} />
        <Route path="quick-check/:kind?" element={<QuickRun />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="register-clinic" element={<Register clinic />} />
      </Route>
      <Route element={<RequireRole roles={["patient"]} />}>
        <Route path="app" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="symptoms" element={<SymptomAssessment />} />
          <Route path="wellness" element={<WellnessAssessment />} />
          <Route path="measurements" element={<Measurements />} />
          <Route path="assessments" element={<Assessments />} />
          <Route path="assessments/:id" element={<AssessmentDetail />} />
          <Route path="appointments" element={<Appointments />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Route>
      <Route element={<RequireRole roles={["clinician", "clinic_admin"]} />}>
        <Route path="clinic" element={<AppShell />}>
          <Route index element={<ClinicHome />} />
          <Route path="calibration" element={<CalibrationPage />} />
          <Route element={<RequireRole roles={["clinician"]} />}>
            <Route path="patients" element={<PatientDirectory />} />
            <Route path="patients/:id" element={<PatientPage />} />
          </Route>
          <Route element={<RequireRole roles={["clinic_admin"]} />}>
            <Route path="team" element={<TeamPage />} />
          </Route>
        </Route>
      </Route>
      <Route element={<RequireRole roles={["researcher"]} />}>
        <Route path="research" element={<AppShell />}>
          <Route index element={<Experiments />} />
          <Route path="datasets" element={<Datasets />} />
          <Route path="models" element={<ModelRegistry />} />
          <Route path="compare" element={<Compare />} />
          <Route path="experiments/:id" element={<ExperimentDashboard />} />
        </Route>
      </Route>
      <Route path="*" element={<PublicLayout />}><Route path="*" element={<Missing />} /></Route>
    </Routes>
    </Suspense>
  );
}
