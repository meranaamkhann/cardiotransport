export type Tone = "good" | "watch" | "action" | "unknown";

export interface Status {
  tone: Tone;
  label: string;
}

export function bloodPressure(systolic?: number, diastolic?: number): Status {
  if (systolic === undefined) return { tone: "unknown", label: "No reading" };
  const d = diastolic ?? 0;
  if (systolic > 180 || d > 120) return { tone: "action", label: "Very high" };
  if (systolic >= 140 || d >= 90) return { tone: "action", label: "Stage 2 range" };
  if (systolic >= 130 || d >= 80) return { tone: "watch", label: "Stage 1 range" };
  if (systolic >= 120) return { tone: "watch", label: "Elevated" };
  return { tone: "good", label: "Normal" };
}

export function cholesterol(value?: number): Status {
  if (value === undefined) return { tone: "unknown", label: "No reading" };
  if (value < 200) return { tone: "good", label: "Desirable" };
  if (value < 240) return { tone: "watch", label: "Borderline high" };
  return { tone: "action", label: "High" };
}

export function glucose(value?: number): Status {
  if (value === undefined) return { tone: "unknown", label: "No reading" };
  if (value < 100) return { tone: "good", label: "Normal" };
  if (value < 126) return { tone: "watch", label: "Prediabetes range" };
  return { tone: "action", label: "Diabetes range" };
}

export const LEVEL_SCORE: Record<string, number> = { routine: 1, soon: 2, prompt: 3, urgent: 4, emergency: 5 };
