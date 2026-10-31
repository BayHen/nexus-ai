import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResourceTable } from "@/components/data/resource-table";

type Row = { id: string; name: string };
const columns = [{ key: "name", label: "Tên", render: (item: Row) => item.name }];

describe("ResourceTable", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders backend data and sends search/filter/pagination parameters", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ items: [{ id: "1", name: "Sản phẩm thật" }], page: 1, page_size: 10, total: 12 }), { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<ResourceTable<Row> endpoint="/api/backend/products" columns={columns} filter={{ name: "status", label: "Trạng thái", options: [{ value: "active", label: "Active" }] }} />);
    expect(await screen.findByText("Sản phẩm thật")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Tìm kiếm"), { target: { value: "coffee" } });
    fireEvent.click(screen.getByRole("button", { name: "Tìm kiếm" }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining("query=coffee"), expect.anything()));
    fireEvent.change(screen.getByRole("combobox", { name: "Trạng thái" }), { target: { value: "active" } });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining("status=active"), expect.anything()));
    fireEvent.click(screen.getByRole("button", { name: "Sau" }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining("page=2"), expect.anything()));
  });

  it("shows an explicit backend error instead of mock data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ error: { code: "backend_unavailable", message: "down" } }), { status: 503, headers: { "Content-Type": "application/json" } }));
    render(<ResourceTable<Row> endpoint="/api/backend/products" columns={columns} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không thể kết nối FastAPI");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
