import type { ApiErrorPayload } from "@/lib/api/types";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    message = "API request failed",
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!value || typeof value !== "object" || !("error" in value)) {
    return false;
  }
  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  );
}

export function normalizeApiError(value: unknown, status: number): ApiErrorPayload {
  if (isApiErrorPayload(value)) {
    return value;
  }

  const message = value instanceof Error ? value.message : "Backend request failed";
  return {
    error: {
      code: status === 503 ? "backend_unavailable" : "unexpected_api_error",
      message,
    },
  };
}

export function toUserMessage(error: ApiError): string {
  if (error.status === 503 || error.code === "backend_unavailable") {
    return "Không thể kết nối FastAPI. Hãy kiểm tra backend và PostgreSQL trước khi thử lại.";
  }
  return "Yêu cầu không hoàn tất. Hãy thử lại hoặc kiểm tra log request tương ứng.";
}

export function apiErrorFromResponse(payload: unknown, status: number): ApiError {
  const normalized = normalizeApiError(payload, status);
  return new ApiError(
    normalized.error.code,
    status,
    normalized.error.message,
    normalized.error.request_id,
  );
}
