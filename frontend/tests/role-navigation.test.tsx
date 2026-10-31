import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Navigation } from "@/components/layout/navigation";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

describe("role-aware navigation", () => {
  it("does not show privileged analytics and team links to viewers", () => {
    render(<Navigation open onClose={() => undefined} role="viewer" />);
    expect(screen.queryByRole("link", { name: "Phân tích" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Đội ngũ" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sản phẩm" })).toBeInTheDocument();
  });

  it("shows management links to owners", () => {
    render(<Navigation open onClose={() => undefined} role="owner" />);
    expect(screen.getByRole("link", { name: "Phân tích" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Đội ngũ" })).toBeInTheDocument();
  });
});
