export type Pathway = "symptomatic" | "referred";
export type Band = "lower" | "moderate" | "higher";
export type Tier = "core" | "clinical";

export interface Calibration {
  tier: Tier;
  intercept: number;
  slope: number;
  label?: string;
  n?: number;
}

export interface AssessmentPayload {
  pathway: Pathway;
  age: number;
  sex: "female" | "male";
  chest_pain: "typical" | "atypical" | "non_anginal" | "none";
  exercise_pain: boolean;
  systolic: number | null;
  cholesterol: number | null;
  fasting_glucose: number | null;
  ecg: "normal" | "st_t_abnormality" | "lv_hypertrophy" | null;
  max_hr: number | null;
  st_depression: number | null;
  emergency: string[];
  local_calibrations: Calibration[];
}

export interface Driver {
  feature: string;
  label: string;
  effect: string;
  log_odds: number;
}

export interface AssessmentResult {
  tier: Tier;
  band: Band;
  band_raised: boolean;
  raised_reason: string | null;
  headline: string;
  summary: string;
  action: string;
  emergency: { active: boolean; message: string | null };
  model_score: number;
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

export interface WellnessPayload {
  age: number;
  sex: "female" | "male";
  systolic: number | null;
  diastolic: number | null;
  cholesterol: number | null;
  fasting_glucose: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  smoking: "never" | "former" | "current";
  diabetes: boolean;
  family_history: boolean;
  activity_minutes: number | null;
  south_asian_cutoffs: boolean;
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
}

export interface HistoryEntry {
  id: string;
  createdAt: string;
  kind: "check" | "wellness";
  title: string;
  subtitle: string;
  check?: AssessmentResult;
  wellness?: WellnessResult;
}

export interface Metrics {
  n: number;
  events: number;
  prevalence: number | null;
  auc: number | null;
  auc_ci: [number, number] | null;
  brier: number | null;
  cal_intercept: number | null;
  cal_slope: number | null;
  sensitivity: number | null;
  specificity: number | null;
}

export interface BandStats {
  n: number;
  events: number;
  rate: number | null;
  ci: [number | null, number | null];
  site_min: number | null;
  site_max: number | null;
  per_site: Record<string, { n: number; events: number; rate: number | null }>;
}

export interface TierCard {
  features: string[];
  held_out_site: Record<string, Metrics>;
  held_out_pooled: Metrics;
  calibration: Record<string, { predicted: number[]; observed: number[] }>;
  bands: { lower_cut: number; higher_cut: number; stats: Record<Band, BandStats> };
  regularisation_C: number;
  coefficients: { term: string; feature: string; coef: number }[];
}

export interface PaperRun {
  features: string[];
  internal: Metrics;
  external: Record<string, Metrics>;
  pooled_external: Metrics;
}

export interface ModelCard {
  version: string;
  trained_at: string;
  data_source: string;
  cohorts: Record<string, { n: number; events: number; prevalence: number; median_age: number; female_pct: number; missing_pct: Record<string, number> }>;
  zero_values_recoded_as_missing: Record<string, { chol: number; trestbps: number; n: number }>;
  deployment: Record<Tier, TierCard>;
  paper_protocol: Record<string, PaperRun> | null;
}

export interface ClinicTierResult {
  tier: Tier;
  method: "none" | "intercept" | "slope";
  intercept: number;
  slope: number;
  n: number;
  events: number;
  observed_rate: number;
  mean_predicted_before: number;
  calibration_intercept_before: number | null;
  calibration_slope_before: number | null;
  brier_before: number;
  brier_after: number;
  slope_update_considered: boolean;
}

export interface ClinicResult {
  n: number;
  events: number;
  site_name: string;
  results: ClinicTierResult[];
}
