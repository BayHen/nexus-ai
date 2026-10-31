import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthForm } from "@/components/auth/auth-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

describe("AuthForm", () => {
  afterEach(() => { vi.restoreAllMocks(); push.mockReset(); });

  it("shows accessible validation errors before calling the API", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<AuthForm mode="login" />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "invalid" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(screen.getByRole("alert")).toHaveTextContent("email hợp lệ");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("uses the real BFF auth contract and routes to organization selection", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ user: {}, tokens: {} }), { status: 200, headers: { "Content-Type": "application/json" } }));
    render(<AuthForm mode="login" />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/organizations"));
    expect(fetch).toHaveBeenCalledWith("/api/backend/auth/login", expect.objectContaining({ method: "POST" }));
  });
});
