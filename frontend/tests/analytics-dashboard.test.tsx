import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";

describe("AnalyticsDashboard", () => {
  it("loads charts, comparison, alerts, and applies a date range", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("inventory/stocks")) return new Response(JSON.stringify({ items: [{ branch_id: "b", branch_name: "Kho chính", product_id: "p", product_name: "Cà phê", product_sku: "SKU", quantity: "2", low_stock_threshold: "5", is_low_stock: true, updated_at: "2026-01-01" }], page: 1, page_size: 10, total: 1 }), { status: 200 });
      if (url.includes("analytics/revenue")) return new Response(JSON.stringify({ currency: "USD", granularity: "day", items: [{ period: "2026-10-01", revenue: "100", order_count: 2 }] }), { status: 200 });
      return new Response(JSON.stringify({ currency: "USD", total_revenue: url.includes("date_from=2026-10-01") ? "100" : "50", gross_revenue: "100", refunded_amount: "0", order_count: 2, average_order_value: "50" }), { status: 200 });
    });
    render(<AnalyticsDashboard />);
    expect(await screen.findByRole("img", { name: "Biểu đồ doanh thu theo ngày" })).toBeInTheDocument();
    expect(screen.getByText("Cà phê")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Từ ngày"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Đến ngày"), { target: { value: "2026-10-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Áp dụng" }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining("date_from=2026-10-01"), expect.anything()));
  });
});
