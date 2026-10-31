import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { isTrustedBrowserMutation } from "@/lib/api/csrf";

describe("BFF CSRF validation", () => {
  it("rejects cross-site mutations", () => {
    const request = new NextRequest("https://app.example.com/api/backend/orders", { method: "POST", headers: { origin: "https://evil.example", "sec-fetch-site": "cross-site" } });
    expect(isTrustedBrowserMutation(request)).toBe(false);
  });

  it("allows same-origin mutations and safe reads", () => {
    const mutation = new NextRequest("https://app.example.com/api/backend/orders", { method: "POST", headers: { origin: "https://app.example.com", "sec-fetch-site": "same-origin" } });
    const read = new NextRequest("https://app.example.com/api/backend/orders", { method: "GET", headers: { origin: "https://evil.example" } });
    expect(isTrustedBrowserMutation(mutation)).toBe(true);
    expect(isTrustedBrowserMutation(read)).toBe(true);
  });
});
