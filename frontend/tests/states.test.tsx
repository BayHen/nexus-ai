import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/states/empty-state";
import { LoadingState } from "@/components/states/loading-state";

describe("shared states", () => {
  it("announces loading state accessibly", () => {
    render(<LoadingState label="Đang kiểm tra API" />);

    expect(screen.getByRole("status")).toHaveTextContent("Đang kiểm tra API");
  });

  it("renders an explicit empty state", () => {
    render(<EmptyState title="Chưa có dữ liệu" description="Dữ liệu sẽ xuất hiện sau." />);

    expect(screen.getByRole("heading", { name: "Chưa có dữ liệu" })).toBeInTheDocument();
    expect(screen.getByText("Dữ liệu sẽ xuất hiện sau.")).toBeInTheDocument();
  });
});
