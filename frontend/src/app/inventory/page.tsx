"use client";

import { EntityPage } from "@/components/data/entity-page";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Stock } from "@/lib/api/types";
export default function InventoryPage() { return <EntityPage<Stock> eyebrow="Operations" title="Tồn kho" description="Số lượng theo chi nhánh, low-stock threshold và trạng thái cảnh báo từ backend." endpoint="/api/backend/inventory/stocks" searchLabel="Tìm tên hoặc SKU sản phẩm" filter={{ name: "low_stock", label: "Cảnh báo", options: [{ value: "true", label: "Sắp hết" }, { value: "false", label: "Ổn định" }] }} columns={[
  { key: "product", label: "Sản phẩm", render: (item) => <div><strong>{item.product_name ?? "Không xác định"}</strong><span className="block font-mono text-xs text-muted">{item.product_sku}</span></div> },
  { key: "branch", label: "Chi nhánh", render: (item) => item.branch_name ?? item.branch_id },
  { key: "quantity", label: "Số lượng", render: (item) => <strong>{item.quantity}</strong> },
  { key: "threshold", label: "Ngưỡng thấp", render: (item) => item.low_stock_threshold },
  { key: "state", label: "Trạng thái", render: (item) => <StatusBadge value={item.is_low_stock ? "Sắp hết" : "Ổn định"} tone={item.is_low_stock ? "danger" : "success"} /> },
]} />; }
