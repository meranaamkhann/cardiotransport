import type { AssessmentPayload, AssessmentResult, ClinicResult, ModelCard, WellnessPayload, WellnessResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const assess = (payload: AssessmentPayload) => request<AssessmentResult>("/api/assess", json(payload));
export const wellness = (payload: WellnessPayload) => request<WellnessResult>("/api/wellness", json(payload));
export const modelCard = () => request<ModelCard>("/api/model-card");

export const calibrateClinic = (file: File, siteName: string) => {
  const form = new FormData();
  form.append("file", file);
  form.append("site_name", siteName);
  return request<ClinicResult>("/api/clinic/calibrate", { method: "POST", body: form });
};
