export type Role = "patient" | "clinician" | "clinic_admin" | "researcher";
export type Level = "routine" | "soon" | "prompt" | "urgent" | "emergency";
export type Band = "lower" | "moderate" | "higher";
export type Tier = "core" | "clinical";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  clinic: { id: number; name: string; code: string | null } | null;
  profile_complete: boolean | null;
}

export interface Profile {
  sex: "female" | "male" | null;
  birth_year: number | null;
  height_cm: number | null;
  smoking: "never" | "former" | "current" | null;
  diabetes: boolean;
  family_history: boolean;
  conditions: string[];
  activity_minutes: number | null;
}

export interface Driver {
  feature: string;
  label: string;
  effect: string;
  log_odds: number;
}

export interface ModelEstimate {
  tier: Tier;
  band: Band;
  band_raised: boolean;
  raised_reason: string | null;
  headline: string;
  summary: string;
  action: string;
  emergency: { active: boolean; message: string | null };
  model_score: number;
  score_range: [number, number] | null;
  second_opinion: { band: Band; agrees: boolean; score: number; model: string } | null;
  local: { probability: number; label: string; n: number | null } | null;
  observed: { n: number; rate: number | null; ci: [number | null, number | null]; site_min: number | null; site_max: number | null };
  drivers: { up: Driver[]; down: Driver[] };
  confidence: { level: "good" | "fair" | "limited"; reasons: string[] };
  warnings: string[];
  next_steps: string[];
  inputs: { label: string; value: string }[];
  data_source: string;
  model_version: string;
}

export interface Triage {
  level: Level;
  title: string;
  message: string;
  reasons: string[];
  limits: string;
}

export interface SymptomResult {
  provenance: Record<string, string>;
  triage: Triage;
  model: ModelEstimate | null;
  model_note: string | null;
  final: { level: Level; title: string; message: string; rule: string };
}

export interface WellnessFactor {
  key: string;
  label: string;
  value: string;
  status: "good" | "watch" | "action" | "unknown";
  detail: string;
  tip: string;
}

export interface WellnessResult {
  overall: "urgent" | "several" | "some" | "good";
  headline: string;
  factors: WellnessFactor[];
  counts: { action: number; watch: number; unknown: number };
  urgent: string[];
  context: string;
  next_steps: string[];
  provenance?: Record<string, string>;
}

export interface AssessmentRecord {
  id: number;
  patient_id: number;
  patient_name: string | null;
  kind: "symptom" | "wellness";
  urgency: Level;
  status: "submitted" | "reviewed";
  model_version: string | null;
  created_at: string;
  reviewed_at: string | null;
  reviewer: string | null;
  headline: string | null;
  inputs?: Record<string, unknown>;
  result?: SymptomResult & WellnessResult;
  clinician_summary?: string | null;
}

export interface Measurement {
  id: number;
  kind: "systolic" | "diastolic" | "cholesterol" | "glucose" | "weight" | "resting_hr";
  value: number;
  unit: string;
  measured_at: string;
}

export interface Appointment {
  id: number;
  scheduled_at: string;
  reason: string;
  status: "requested" | "confirmed" | "completed" | "cancelled";
  clinician: string | null;
}

export type AppointmentRecord = Appointment;

export interface Dashboard {
  user: User;
  profile: Profile;
  total_assessments: number;
  recent: AssessmentRecord[];
  latest_measurements: Record<string, number>;
  upcoming: Appointment[];
}

export interface PatientRow {
  id: number;
  name: string;
  email: string;
  last_assessment: AssessmentRecord | null;
  pending_review: number;
}

export interface PatientDetail {
  patient: { id: number; name: string; email: string };
  profile: Profile;
  assessments: AssessmentRecord[];
  measurements: Measurement[];
  notes: { id: number; author: string; assessment_id: number | null; body: string; created_at: string }[];
  appointments: Appointment[];
}

export interface CalibrationRow {
  id: number;
  tier: Tier;
  method: string;
  intercept: number;
  slope: number;
  n: number;
  events: number;
  brier_before: number;
  brier_after: number;
  is_active: boolean;
  created_at: string;
}

export interface CalibrationPreview {
  n: number;
  events: number;
  applied: boolean;
  results: {
    tier: Tier;
    method: string;
    n: number;
    observed_rate: number;
    mean_predicted_before: number;
    brier_before: number;
    brier_after: number;
    slope_update_considered: boolean;
  }[];
}

export interface StaffUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface AuditRow {
  id: number;
  actor: string;
  action: string;
  entity: string;
  entity_id: number | null;
  created_at: string;
}

export interface Metrics {
  n: number;
  events: number;
  prevalence: number | null;
  auc: number | null;
  auc_ci: [number, number] | null;
  average_precision: number | null;
  brier: number | null;
  brier_ci: [number, number] | null;
  sensitivity: number | null;
  specificity: number | null;
  precision: number | null;
  f1: number | null;
  balanced_accuracy: number | null;
  cal_intercept: number | null;
  cal_slope: number | null;
}

export interface Curve {
  fpr: number[];
  tpr: number[];
}

export interface Bins {
  predicted: number[];
  observed: number[];
  n: number[];
}

export interface DecisionCurve {
  thresholds: number[];
  model: number[];
  prevalence_adjusted: number[];
  treat_all: number[];
  treat_none: number[];
}

export interface ModelRun {
  features: string[];
  kind: "logistic" | "forest";
  internal: Metrics;
  external: Record<string, Metrics>;
  pooled_external: Metrics;
  roc: Record<string, Curve | null>;
  calibration: Record<string, Bins | null>;
  dca: Record<string, DecisionCurve>;
  interpretability: {
    method: string;
    coefficients?: { term: string; feature: string; value: number }[];
    impurity?: { feature: string; value: number }[];
    permutation?: { feature: string; value: number; sd: number }[];
  };
}

export interface ExperimentResult {
  meta: {
    name: string;
    provenance: string;
    provenance_label: string;
    data_source: string;
    dev_site: string;
    recode_zeros: boolean;
    bootstrap: number;
    folds: number;
    repeats: number;
    extension_analyses: string[];
  };
  dev_site: string;
  sites_external: string[];
  cohorts: Record<string, { n: number; events: number; prevalence: number }>;
  missingness: Record<string, Record<string, number>>;
  availability: Record<string, { worst_missing_pct: number; portable: boolean }>;
  features: string[];
  models: Record<string, ModelRun>;
  recalibration: Record<string, Record<string, {
    prevalence_adjusted: { brier_before: number; brier_after: number; note: string };
    update_study: Record<string, { none: number; intercept: number; intercept_slope: number }>;
    full_update: { intercept: { shift: number; brier: number }; intercept_slope: { intercept: number; slope: number; brier: number }; brier_before: number; note: string } | null;
  }>>;
  subgroup: { model: string; column: string | null; rows: { evaluation: string; group: string; n: number; events: number; auc: number | null; auc_ci: [number, number] | null; sensitivity: number; specificity: number }[] };
  verdicts: { site: string; level: "ok" | "warn"; status: string }[];
  verdict_model: string;
  comparison_with_paper?: { label: string; paper: number; reproduced: number; difference: number }[];
  notes: string[];
}

export interface Experiment {
  id: number;
  name: string;
  kind: "paper_replication" | "custom_validation";
  provenance: "reproduced" | "new_experiment" | "synthetic_demo";
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  dataset_id: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  config?: Record<string, unknown>;
  result?: ExperimentResult | null;
}

export interface DatasetColumn {
  name: string;
  kind: "numeric" | "categorical";
  missing_pct: number;
  n_unique: number;
}

export interface Dataset {
  id: number;
  name: string;
  n_rows: number;
  columns: DatasetColumn[];
  sha256: string;
  created_at: string;
  warnings?: string[];
}

export interface TierCard {
  features: string[];
  held_out_site: Record<string, Metrics>;
  forest_held_out_site: Record<string, Metrics>;
  agreement: { same_band_pct: number; disease_rate_when_models_disagree: number | null; disagreements: number };
  bootstrap_models: number;
  held_out_pooled: Metrics;
  calibration: Record<string, Bins | null>;
  bands: { lower_cut: number; higher_cut: number; stats: Record<Band, { n: number; events: number; rate: number | null; ci: [number | null, number | null]; site_min: number | null; site_max: number | null }> };
  regularisation_C: number;
}

export interface ModelCard {
  version: string;
  trained_at: string;
  data_source: string;
  cohorts: Record<string, { n: number; events: number; prevalence: number; median_age: number; female_pct: number }>;
  zero_values_recoded_as_missing: Record<string, { chol: number; trestbps: number; n: number }>;
  deployment: Record<Tier, TierCard>;
}

export interface ModelVersion {
  id: number;
  tag: string;
  version: string;
  data_source: string;
  trained_at: string;
  is_active: boolean;
  card: ModelCard;
}

export interface AccessLogRow {
  id: number;
  who: string;
  action: string;
  when: string;
}
