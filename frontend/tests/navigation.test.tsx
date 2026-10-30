import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/layout/app-shell";

describe("AppShell navigation", () => {
  it("opens and closes the responsive navigation", () => {
    render(
      <AppShell>
        <p>Dashboard content</p>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mở menu điều hướng" }));
    expect(screen.getByRole("button", { name: "Đóng menu điều hướng" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Đóng menu" }));
    expect(screen.queryByRole("button", { name: "Đóng menu điều hướng" })).not.toBeInTheDocument();
  });
});
