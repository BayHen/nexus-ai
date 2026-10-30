export type HealthStatus = "alive" | "ready" | "not_ready";

export type HealthResponse = {
  status: HealthStatus;
  checks: Record<string, "up" | "down"> | null;
};

export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
};

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (!value || typeof value !== "object" || !("status" in value) || !("checks" in value)) {
    return false;
  }
  const statusIsValid = ["alive", "ready", "not_ready"].includes(String(value.status));
  const checksAreValid =
    value.checks === null ||
    (typeof value.checks === "object" &&
      Object.values(value.checks).every((check) => check === "up" || check === "down"));
  return statusIsValid && checksAreValid;
}
