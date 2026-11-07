import { request } from "./api";
import { authHeader } from "./session";
import type { Role } from "./session";
import type { AssessmentPayload, AssessmentResult, PaperRun, WellnessPayload, WellnessResult } from "./types";

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface TokenOut { access_token: string; role: Role; name: string }
export const login = (email: string, password: string) => request<TokenOut>("/api/auth/login", post({ email, password }));
export const register = (body: { email: string; name: string; password: string; clinic?: string }) =>
  request<TokenOut>("/api/auth/register", post(body));

export const saveSymptom = (payload: AssessmentPayload) =>
  request<{ id: number; result: AssessmentResult }>("/api/patient/assessments/symptom", post(payload));
export const saveWellness = (payload: WellnessPayload) =>
  request<{ id: number; result: WellnessResult }>("/api/patient/assessments/wellness", post(payload));

export interface ResultLite {
  headline?: string;
  summary?: string;
  action?: string;
  emergency?: { active: boolean; message: string | null };
  drivers?: { up: { label: string; effect: string }[] };
}
export interface Note { id: number; author: string; body: string; created_at: string; source: string }
export interface RecordRow { id: number; kind: string; band: string | null; emergency: boolean; status: string; created_at: string; model_version: string }
export interface RecordDetail extends RecordRow { result: ResultLite; notes: Note[] }
export interface PatientRow { id: number; name: string; email: string; assessments: number; pending_review: number; last_assessment: string | null }

export const myRecords = () => request<RecordRow[]>("/api/patient/assessments");
export const myRecord = (id: number) => request<RecordDetail>(`/api/patient/assessments/${id}`);
export const patients = () => request<PatientRow[]>("/api/clinic/patients");
export const patientRecords = (id: number) => request<RecordDetail[]>(`/api/clinic/patients/${id}/assessments`);
export const addNote = (id: number, body: string) => request<RecordDetail>(`/api/clinic/assessments/${id}/notes`, post({ body }));

export async function downloadHistory() {
  const response = await fetch("/api/patient/export.csv", { headers: authHeader() });
  if (!response.ok) throw new Error("Could not download your history.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "cardiolens_history.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export interface SiteMetrics {
  n: number; prev: number; auc: number | null; auc_ci?: [number, number]; brier: number;
  sens: number; spec: number; cal_intercept: number | null; cal_slope: number | null;
}
export interface Report {
  meta: { name: string; target: string; dev_site: string; group_col: string | null; features: string[]; portable: string[]; dropped: string[] };
  sites: Record<string, { n: number; prev: number; missing: Record<string, number> }>;
  internal: Record<string, SiteMetrics>;
  external: Record<string, Record<string, SiteMetrics>>;
  calib: Record<string, { x: number[]; y: number[] }>;
  dca: Record<string, { t: number[]; raw: number[]; adjusted: number[]; all: number[] }>;
  update: Record<string, Record<string, number[]>>;
  adjusted: Record<string, { raw: number; adj: number }>;
  subgroup: Record<string, SiteMetrics>;
  verdicts: { site: string; level: string; status: string }[];
  warnings: string[];
  provenance: { origin: string; note: string };
}
export interface ExperimentRow { id: number; name: string; origin: string; created_at: string }
export interface CsvInfo { rows: number; columns: { name: string; values: string[] | null }[] }

export const experiments = () => request<ExperimentRow[]>("/api/research/experiments");
export const experiment = (id: number) => request<{ id: number; name: string; origin: string; result: Report }>(`/api/research/experiments/${id}`);
export const runDemo = () => request<ExperimentRow>("/api/research/experiments/demo", { method: "POST" });
export const runUpload = (form: FormData) => request<ExperimentRow>("/api/research/experiments", { method: "POST", body: form });
export const inspectCsv = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<CsvInfo>("/api/research/inspect", { method: "POST", body: form });
};
export const paperResults = () =>
  request<{ data_source: string; paper_protocol: Record<string, PaperRun> | null; provenance: string; note: string }>("/api/research/paper-results");
