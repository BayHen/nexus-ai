"use client";

import { EntityPage } from "@/components/data/entity-page";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Member } from "@/lib/api/types";
export default function TeamPage() { return <EntityPage<Member> eyebrow="Access control" title="Đội ngũ" description="Membership và vai trò được backend RBAC kiểm soát; ẩn navigation không thay thế authorization." endpoint="/api/backend/members" searchLabel="Tìm email thành viên" filter={{ name: "role", label: "Vai trò", options: [{ value: "admin", label: "Admin" }, { value: "manager", label: "Manager" }, { value: "staff", label: "Staff" }, { value: "viewer", label: "Viewer" }] }} columns={[
  { key: "email", label: "Thành viên", render: (item) => <strong>{item.email}</strong> },
  { key: "role", label: "Vai trò", render: (item) => <span className="capitalize">{item.role}</span> },
  { key: "status", label: "Trạng thái", render: (item) => <StatusBadge value={item.status} tone={item.status === "active" ? "success" : "warning"} /> },
  { key: "joined", label: "Ngày tham gia", render: (item) => new Date(item.created_at).toLocaleDateString("vi-VN") },
]} />; }
