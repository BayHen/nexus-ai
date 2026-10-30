import { NextResponse } from "next/server";

import { normalizeApiError } from "@/lib/api/errors";
import { isHealthResponse } from "@/lib/api/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const baseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${baseUrl}/health/ready`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
    const payload: unknown = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        normalizeApiError(payload, response.status),
        { status: response.status },
      );
    }

    if (!isHealthResponse(payload)) {
      return NextResponse.json(
        normalizeApiError(new Error("Backend returned an invalid health response"), 502),
        { status: 502 },
      );
    }

    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    return NextResponse.json(normalizeApiError(error, 503), { status: 503 });
  }
}
