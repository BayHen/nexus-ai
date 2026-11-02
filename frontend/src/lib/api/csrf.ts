import type { NextRequest } from "next/server";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function getTrustedOrigins(): Set<string> {
  const raw = process.env.NEXUS_ALLOWED_BROWSER_ORIGINS ?? "";

  return new Set(
    raw
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
      .map((value) => new URL(value).origin)
  );
}

export function isTrustedBrowserMutation(
  request: NextRequest
): boolean {
  if (SAFE_METHODS.has(request.method)) {
    return true;
  }

  const fetchSite = request.headers.get("sec-fetch-site");

  if (fetchSite === "cross-site") {
    return false;
  }

  const origin = request.headers.get("origin");

  // Browser mutations must provide a valid Origin.
  // Non-browser clients need a separately designed
  // authentication/CSRF policy.
  if (!origin || origin === "null") {
    return false;
  }

  try {
    const parsedOrigin = new URL(origin);

    if (!["http:", "https:"].includes(parsedOrigin.protocol)) {
      return false;
    }

    return getTrustedOrigins().has(parsedOrigin.origin);
  } catch {
    return false;
  }
}
