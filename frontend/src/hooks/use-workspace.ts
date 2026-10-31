"use client";

import { useSyncExternalStore } from "react";
import type { Role } from "@/lib/api/types";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

const serverSnapshot = () => "viewer|Chưa chọn tổ chức";
const clientSnapshot = () => `${sessionStorage.getItem("nexus_role") ?? "viewer"}|${sessionStorage.getItem("nexus_organization_name") ?? "Chưa chọn tổ chức"}`;

export function useWorkspace() {
  const snapshot = useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
  const [role, name] = snapshot.split("|", 2) as [Role, string];
  return { role, name };
}
