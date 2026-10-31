"use client";

import { EntityPage } from "@/components/data/entity-page";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Product } from "@/lib/api/types";

export default function ProductsPage() {
  return <EntityPage<Product> eyebrow="Catalog" title="Sản phẩm" description="Tìm kiếm và theo dõi catalog thực của active organization." endpoint="/api/backend/products" searchLabel="Tìm theo tên hoặc SKU" filter={{ name: "status", label: "Trạng thái", options: [{ value: "active", label: "Active" }, { value: "draft", label: "Draft" }, { value: "archived", label: "Archived" }] }} columns={[
    { key: "product", label: "Sản phẩm", render: (item) => <div><strong>{item.name}</strong><span className="mt-1 block font-mono text-xs text-muted">{item.sku}</span></div> },
    { key: "price", label: "Giá", render: (item) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "USD" }).format(Number(item.price)) },
    { key: "status", label: "Trạng thái", render: (item) => <StatusBadge value={item.status} tone={item.status === "active" ? "success" : item.status === "archived" ? "neutral" : "warning"} /> },
    { key: "updated", label: "Cập nhật", render: (item) => new Date(item.updated_at).toLocaleDateString("vi-VN") },
  ]} />;
}
