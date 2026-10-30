import { apiErrorFromResponse, ApiError } from "@/lib/api/errors";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("network_error", 503, "Network request failed");
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("invalid_response", response.status, "API returned invalid JSON");
  }

  if (!response.ok) {
    throw apiErrorFromResponse(payload, response.status);
  }
  return payload as T;
}

export const apiClient = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },
};
