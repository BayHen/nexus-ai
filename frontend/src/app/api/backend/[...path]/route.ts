import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const ACCESS_COOKIE = "nexus_access_token";
const REFRESH_COOKIE = "nexus_refresh_token";
type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  const backendUrl = new URL(`/api/v1/${path.join("/")}`, process.env.API_BASE_URL ?? "http://127.0.0.1:8000");
  backendUrl.search = request.nextUrl.search;
  const cookieStore = await cookies();
  const headers = new Headers({ Accept: "application/json" });
  const accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const idempotencyKey = request.headers.get("idempotency-key");
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  let body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
  const route = path.join("/");
  if (route === "auth/logout") {
    body = JSON.stringify({ refresh_token: cookieStore.get(REFRESH_COOKIE)?.value ?? "missing" });
    headers.set("Content-Type", "application/json");
  }
  let backendResponse: Response;
  try {
    backendResponse = await fetch(backendUrl, { method: request.method, headers, body: body || undefined, cache: "no-store" });
  } catch {
    return NextResponse.json({ error: { code: "backend_unavailable", message: "FastAPI backend is unavailable." } }, { status: 503 });
  }
  const responseText = await backendResponse.text();
  let response = new NextResponse(responseText || null, { status: backendResponse.status, headers: { "Content-Type": backendResponse.headers.get("content-type") ?? "application/json" } });
  if (backendResponse.ok && (route === "auth/login" || route === "auth/register")) {
    const payload = JSON.parse(responseText) as { user: unknown; tokens: { access_token: string; refresh_token: string } };
    response = NextResponse.json({ user: payload.user }, { status: backendResponse.status });
    const secure = process.env.NODE_ENV === "production";
    response.cookies.set(ACCESS_COOKIE, payload.tokens.access_token, { httpOnly: true, sameSite: "lax", secure, path: "/", maxAge: 15 * 60 });
    response.cookies.set(REFRESH_COOKIE, payload.tokens.refresh_token, { httpOnly: true, sameSite: "strict", secure, path: "/api/backend/auth", maxAge: 7 * 24 * 60 * 60 });
  }
  if (route === "auth/logout") {
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(REFRESH_COOKIE);
  }
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
