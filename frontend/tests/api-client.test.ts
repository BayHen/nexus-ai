import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

describe("apiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a typed successful response", async () => {
    const payload: HealthResponse = { status: "ready", checks: { database: "up" } };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiClient.get<HealthResponse>("/health")).resolves.toEqual(payload);
  });

  it("throws the centralized API error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "backend_unavailable", message: "Unavailable", request_id: "req-1" },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(apiClient.get("/health")).rejects.toMatchObject({
      code: "backend_unavailable",
      status: 503,
      requestId: "req-1",
    });
  });
});
