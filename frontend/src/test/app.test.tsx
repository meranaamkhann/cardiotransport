import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api, ApiError, tokenStore } from "../api/client";
import type { AssessmentRecord, Experiment, ModelCard, ModelVersion, PatientDetail, User } from "../api/types";
import App from "../App";
import AssessmentView from "../components/AssessmentView";
import ExperimentDashboard from "../pages/research/Dashboard";
import { ModelRegistry } from "../pages/research/Datasets";
import HowItWorks from "../pages/public/HowItWorks";
import { SymptomAssessment } from "../pages/patient/Assess";
import { PatientPage, ReviewQueue } from "../pages/clinic/Workspace";
import { ProfilePage } from "../pages/patient/Records";
import Compare from "../pages/research/Compare";
import { Route, Routes } from "react-router-dom";
import dashboard from "./fixtures/dashboard.json";
import experiment from "./fixtures/experiment.json";
import modelCard from "./fixtures/model_card.json";
import patientDetail from "./fixtures/patient_detail.json";
import registry from "./fixtures/registry.json";
import symptom from "./fixtures/symptom.json";
import user from "./fixtures/user.json";
import wellness from "./fixtures/wellness.json";
import { mockApi, renderApp } from "./helpers";

const patient = user as unknown as User;

describe("api client", () => {
  it("maps validation errors and surfaces server messages", async () => {
    mockApi(() => ({ status: 422, body: { detail: [{ msg: "Field required" }, { msg: "Too short" }] } }));
    await expect(api("/x")).rejects.toThrow("Field required; Too short");
  });

  it("clears the session on 401", async () => {
    tokenStore.set("stale");
    const listener = vi.fn();
    window.addEventListener("cardiolens:signed-out", listener);
    mockApi(() => ({ status: 401, body: { detail: "Invalid or expired token" } }));
    await expect(api("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(tokenStore.get()).toBeNull();
    expect(listener).toHaveBeenCalled();
    window.removeEventListener("cardiolens:signed-out", listener);
  });

  it("reports an unreachable server clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await expect(api("/health")).rejects.toThrow(/could not reach the server/i);
  });
});

describe("authentication and routing", () => {
  it("redirects visitors from protected pages to sign in", async () => {
    mockApi(() => undefined);
    renderApp(<App />, "/app/symptoms");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows the server message when credentials are wrong", async () => {
    mockApi(() => ({ status: 401, body: { detail: "Incorrect email or password." } }));
    renderApp(<App />, "/login");
    await userEvent.type(await screen.findByLabelText("Email"), "pat@example.org");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpassword1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Incorrect email or password.")).toBeInTheDocument();
  });

  it("signs a patient in and lands on their overview", async () => {
    mockApi((url) => {
      if (url.endsWith("/auth/login")) return { body: { access_token: "token", token_type: "bearer", user: patient } };
      if (url.endsWith("/me/dashboard")) return { body: dashboard };
      return undefined;
    });
    renderApp(<App />, "/login");
    await userEvent.type(await screen.findByLabelText("Email"), "p@x.org");
    await userEvent.type(screen.getByLabelText("Password"), "Str0ngPassw0rd");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: /Hello, Pat/ })).toBeInTheDocument();
    expect(tokenStore.get()).toBe("token");
  });

  it("keeps a patient out of the clinician workspace", async () => {
    tokenStore.set("token");
    mockApi((url) => {
      if (url.endsWith("/auth/me")) return { body: patient };
      if (url.endsWith("/me/dashboard")) return { body: dashboard };
      return undefined;
    });
    renderApp(<App />, "/clinic");
    expect(await screen.findByRole("heading", { name: /Hello, Pat/ })).toBeInTheDocument();
  });
});

describe("symptom assessment workflow", () => {
  it("shows emergency guidance as soon as a warning sign is ticked", async () => {
    mockApi((url) => (url.endsWith("/me/dashboard") ? { body: dashboard } : undefined));
    renderApp(<SymptomAssessment />);
    await userEvent.click(await screen.findByLabelText(/started at rest and has lasted more than 15 minutes/));
    expect(await screen.findByRole("alert")).toHaveTextContent(/call your local emergency number/i);
    expect(screen.getByRole("link", { name: "Call 112" })).toHaveAttribute("href", "tel:112");
  });

  it("will not move past the symptoms step without the required answers", async () => {
    const spy = mockApi((url) => (url.endsWith("/me/dashboard") ? { body: dashboard } : undefined));
    renderApp(<SymptomAssessment />);
    await userEvent.click(await screen.findByRole("button", { name: "Continue" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText(/choose the chest discomfort option/i)).toBeInTheDocument();
    expect(spy.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("walks through every step, shows a review, and submits once", async () => {
    const spy = mockApi((url, init) => {
      if (url.endsWith("/me/dashboard")) return { body: dashboard };
      if (url.endsWith("/me/assessments/symptom") && init?.method === "POST") return { status: 201, body: symptom };
      return undefined;
    });
    renderApp(<Routes><Route path="/" element={<SymptomAssessment />} /><Route path="/app/assessments/:id" element={<p>saved</p>} /></Routes>);
    await userEvent.click(await screen.findByRole("button", { name: "Continue" }));
    await userEvent.click(await screen.findByLabelText(/Pressure or tightness with effort/));
    await userEvent.click(screen.getByRole("radio", { name: "Yes" }));
    await userEvent.selectOptions(screen.getByLabelText("How long have you had them?"), "weeks");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Check your answers")).toBeInTheDocument();
    expect(screen.getByText(/brought on by effort/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Get my assessment" }));
    expect(await screen.findByText("saved")).toBeInTheDocument();
    const posts = spy.mock.calls.filter(([, init]) => init?.method === "POST");
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0][1]?.body))).toMatchObject({ chest_discomfort: "typical", discomfort_with_effort: true, duration: "weeks" });
    expect(window.sessionStorage.getItem("cardiolens.symptom.draft")).toBeNull();
  });

  it("restores a half-finished draft after a reload", async () => {
    window.sessionStorage.setItem("cardiolens.symptom.draft", JSON.stringify({ step: 1, form: { chest: "atypical", duration: "days", effort: "no", breath: "none", severity: "6", emergency: [], conditions: [] } }));
    mockApi((url) => (url.endsWith("/me/dashboard") ? { body: dashboard } : undefined));
    renderApp(<SymptomAssessment />);
    expect(await screen.findByLabelText(/Some of those features/)).toBeChecked();
  });

  it("asks patients with an incomplete profile to finish it", async () => {
    const incomplete = { ...dashboard, user: { ...dashboard.user, profile_complete: false } };
    mockApi((url) => (url.endsWith("/me/dashboard") ? { body: incomplete } : undefined));
    renderApp(<SymptomAssessment />);
    expect(await screen.findByText(/complete your profile first/i)).toBeInTheDocument();
  });
});

describe("assessment records", () => {
  it("keeps patient-reported, rule-based, model-generated and clinician-reviewed information apart", () => {
    renderApp(<AssessmentView a={symptom as unknown as AssessmentRecord} />);
    expect(screen.getByText("Entered by the patient")).toBeInTheDocument();
    expect(screen.getByText("Rule-based, not a diagnosis")).toBeInTheDocument();
    expect(screen.getByText("Model-generated")).toBeInTheDocument();
    expect(screen.getByText("Written by a clinician")).toBeInTheDocument();
    expect(screen.getByText("Arrange ECG and stress test.")).toBeInTheDocument();
  });

  it("renders wellness assessments as a guideline review, not a prediction", () => {
    renderApp(<AssessmentView a={wellness as unknown as AssessmentRecord} />);
    expect(screen.getByText(/Not a prediction or a diagnosis/)).toBeInTheDocument();
    expect(screen.getByText("No clinician has reviewed this assessment yet.")).toBeInTheDocument();
  });

  it("lets a clinician review an assessment from the patient page", async () => {
    const detail = { ...patientDetail, assessments: patientDetail.assessments.map((a, i) => (i === 0 ? { ...a, status: "submitted", clinician_summary: null, reviewer: null, reviewed_at: null } : a)) };
    const spy = mockApi((url, init) => {
      if (url.endsWith(`/clinic/patients/${detail.patient.id}`)) return { body: detail as unknown as PatientDetail };
      if (url.includes("/review") && init?.method === "POST") return { body: {} };
      return undefined;
    });
    renderApp(<Routes><Route path="/clinic/patients/:id" element={<PatientPage />} /></Routes>, `/clinic/patients/${detail.patient.id}`);
    const box = await screen.findByLabelText("Your review");
    await userEvent.type(box, "Looks consistent with exertional angina.");
    await userEvent.click(screen.getByRole("button", { name: "Mark as reviewed" }));
    await waitFor(() => expect(spy.mock.calls.some(([u, i]) => String(u).includes("/review") && i?.method === "POST")).toBe(true));
  });
});

describe("model transparency", () => {
  it("shows the score range and flags a disagreeing second opinion", () => {
    const base = symptom as unknown as AssessmentRecord;
    const model = { ...base.result!.model!, score_range: [40, 71] as [number, number], second_opinion: { band: "lower" as const, agrees: false, score: 21, model: "random forest" } };
    renderApp(<AssessmentView a={{ ...base, result: { ...base.result!, model } } as AssessmentRecord} />);
    expect(screen.getByText(/plausible range 40 to 71/)).toBeInTheDocument();
    expect(screen.getByText(/treat this result as less certain/)).toBeInTheDocument();
  });
});

describe("patient conveniences", () => {
  it("labels blood pressure with guideline categories", async () => {
    const { bloodPressure, cholesterol, glucose } = await import("../components/status");
    expect(bloodPressure(118, 76).label).toBe("Normal");
    expect(bloodPressure(135, 70).label).toBe("Stage 1 range");
    expect(bloodPressure(150, 95).tone).toBe("action");
    expect(cholesterol(245).label).toBe("High");
    expect(glucose(110).label).toBe("Prediabetes range");
    expect(bloodPressure(undefined).tone).toBe("unknown");
  });

  it("requires a password before deleting an account and signs out afterwards", async () => {
    tokenStore.set("token");
    const spy = mockApi((url, init) => {
      if (url.endsWith("/auth/me")) return { body: { ...patient, clinic: null } };
      if (url.endsWith("/me/profile")) return { body: { sex: "male", birth_year: 1968, height_cm: 172, smoking: "former", diabetes: false, family_history: false, conditions: [], activity_minutes: 0 } };
      if (url.endsWith("/me/access-log")) return { body: [{ id: 1, who: "Dr. Rao", action: "patient record viewed", when: "2026-11-01T10:00:00Z" }] };
      if (url.endsWith("/me/delete-account") && init?.method === "POST") return { status: 204 };
      return undefined;
    });
    renderApp(<ProfilePage />);
    expect(await screen.findByText("Dr. Rao")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(screen.getByRole("button", { name: "Delete permanently" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Enter your password to confirm"), "Str0ngPassw0rd");
    await userEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(spy.mock.calls.some(([u]) => String(u).endsWith("/me/delete-account"))).toBe(true));
    await waitFor(() => expect(tokenStore.get()).toBeNull());
  });

  it("remembers the larger text preference", async () => {
    mockApi(() => undefined);
    renderApp(<App />, "/");
    await userEvent.click(await screen.findByRole("button", { name: "Larger text" }));
    expect(document.documentElement.dataset.size).toBe("large");
    expect(window.localStorage.getItem("cardiolens.size")).toBe("large");
  });
});

describe("clinician queue", () => {
  const rows = [
    { id: 1, patient_id: 5, patient_name: "Kabir Singh", kind: "symptom", urgency: "emergency", status: "submitted", headline: "Call emergency services now", created_at: "2026-11-01T10:00:00Z" },
    { id: 2, patient_id: 6, patient_name: "Meera Nair", kind: "symptom", urgency: "soon", status: "submitted", headline: "See a doctor in the coming weeks", created_at: "2026-11-02T10:00:00Z" },
  ];

  it("highlights emergencies and filters by urgency and name", async () => {
    mockApi((url) => (url.endsWith("/clinic/queue") ? { body: rows } : undefined));
    renderApp(<ReviewQueue />);
    expect(await screen.findByText(/1 emergency-level assessment waiting/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Soon/ }));
    expect(screen.queryByText("Kabir Singh")).not.toBeInTheDocument();
    expect(screen.getByText("Meera Nair")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^All/ }));
    await userEvent.type(screen.getByLabelText("Search patients"), "kabir");
    expect(screen.queryByText("Meera Nair")).not.toBeInTheDocument();
  });
});

describe("compare experiments", () => {
  it("shows metric differences between two completed runs", async () => {
    const exp = experiment as unknown as Experiment;
    const other = JSON.parse(JSON.stringify(exp)) as Experiment;
    other.id = exp.id + 1;
    other.name = "Recoded run";
    other.result!.meta.recode_zeros = true;
    other.result!.models.portable_logistic.external.Hungary.auc = 0.9;
    mockApi((url) => {
      if (url.endsWith("/research/experiments")) return { body: [exp, other] };
      if (url.endsWith(`/research/experiments/${exp.id}`)) return { body: exp };
      if (url.endsWith(`/research/experiments/${other.id}`)) return { body: other };
      return undefined;
    });
    renderApp(<Compare />);
    await userEvent.selectOptions(await screen.findByLabelText("Run A (baseline)"), String(exp.id));
    await userEvent.selectOptions(screen.getByLabelText("Run B"), String(other.id));
    expect(await screen.findByText("What differs between the runs")).toBeInTheDocument();
    expect(screen.getByText("recoded as missing")).toBeInTheDocument();
    expect(screen.getByText("Metric differences")).toBeInTheDocument();
  });
});

describe("research dashboard", () => {
  const exp = experiment as unknown as Experiment;

  function open() {
    mockApi((url) => (url.includes("/research/experiments/") ? { body: exp } : undefined));
    renderApp(<Routes><Route path="/research/experiments/:id" element={<ExperimentDashboard />} /></Routes>, `/research/experiments/${exp.id}`);
  }

  it("labels synthetic results and shows the comparison with the paper", async () => {
    open();
    expect(await screen.findByText("Synthetic demonstration")).toBeInTheDocument();
    expect(screen.getByText(/describe generated records/i)).toBeInTheDocument();
    expect(screen.getByText("Comparison with the paper")).toBeInTheDocument();
  });

  it("steps through every analysis tab without errors", async () => {
    open();
    await screen.findByText("Comparison with the paper");
    for (const [tab, expected] of [["Performance", /Discrimination by cohort/], ["ROC", /ROC curves/], ["Calibration", /Calibration:/], ["Decision curves", /Additional analysis, not in the paper/],
      ["Missing data", /Missing-data heatmap/], ["Features", /Interpretability/], ["Subgroups", /Subgroup performance/], ["Recalibration", /Extension analysis/]] as const) {
      await userEvent.click(screen.getByRole("tab", { name: tab }));
      expect(await screen.findByText(expected)).toBeInTheDocument();
    }
  });

  it("explains a failed experiment", async () => {
    mockApi(() => ({ body: { ...exp, status: "failed", result: null, error: "UCI files not found" } }));
    renderApp(<Routes><Route path="/research/experiments/:id" element={<ExperimentDashboard />} /></Routes>, "/research/experiments/1");
    expect(await screen.findByText("UCI files not found")).toBeInTheDocument();
  });

  it("shows the model registry with the active model", async () => {
    mockApi(() => ({ body: registry as unknown as ModelVersion[] }));
    renderApp(<ModelRegistry />);
    expect(await screen.findByText("Active")).toBeInTheDocument();
  });
});

describe("public evidence page", () => {
  it("renders the model card including held-out hospital results", async () => {
    mockApi(() => ({ body: modelCard as unknown as ModelCard }));
    renderApp(<HowItWorks />);
    expect(await screen.findByText("Three separate layers")).toBeInTheDocument();
    const table = screen.getByText("What each band has meant in the records").closest("section") as HTMLElement;
    expect(within(table).getByText("Lower concern")).toBeInTheDocument();
  });

  it("shows an error state with a retry when the card cannot load", async () => {
    mockApi(() => ({ status: 503, body: { detail: "The model has not been trained yet." } }));
    renderApp(<HowItWorks />);
    expect(await screen.findByText("The model has not been trained yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
