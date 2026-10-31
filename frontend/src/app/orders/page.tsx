"use client";

import { EntityPage } from "@/components/data/entity-page";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Order } from "@/lib/api/types";
export default function OrdersPage() { return <EntityPage<Order> eyebrow="Commerce" title="Đơn hàng" description="Theo dõi order state và tổng tiền do server tính toán." endpoint="/api/backend/orders" searchable={false} filter={{ name: "status", label: "Trạng thái", options: [{ value: "draft", label: "Draft" }, { value: "confirmed", label: "Confirmed" }, { value: "completed", label: "Completed" }, { value: "cancelled", label: "Cancelled" }] }} columns={[
  { key: "id", label: "Mã đơn", render: (item) => <span className="font-mono text-xs">{item.id.slice(0, 12)}…</span> },
  { key: "status", label: "Trạng thái", render: (item) => <StatusBadge value={item.status} tone={item.status === "completed" ? "success" : item.status === "cancelled" ? "danger" : "warning"} /> },
  { key: "items", label: "Dòng hàng", render: (item) => item.items.length },
  { key: "total", label: "Tổng tiền", render: (item) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "USD" }).format(Number(item.total_amount)) },
  { key: "created", label: "Ngày tạo", render: (item) => new Date(item.created_at).toLocaleDateString("vi-VN") },
]} />; }
