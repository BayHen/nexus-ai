"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type { UserProfile } from "@/lib/api/types";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";

export function AccountPanel() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { apiClient.get<UserProfile>("/api/backend/auth/me").then(setProfile).catch(() => setError(true)); }, []);
  async function logout() {
    await apiClient.post("/api/backend/auth/logout");
    sessionStorage.clear();
    router.push("/login");
  }
  if (error) return <ErrorState title="Không thể tải tài khoản" description="Phiên đăng nhập đã hết hạn hoặc backend không khả dụng." />;
  if (!profile) return <LoadingState label="Đang tải tài khoản" />;
  return <section className="mb-6 flex flex-col gap-5 border border-line bg-panel p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs uppercase tracking-wider text-muted">Email đăng nhập</p><strong className="mt-2 block">{profile.email}</strong><span className="mt-1 block text-xs text-muted">Tạo ngày {new Date(profile.created_at).toLocaleDateString("vi-VN")}</span></div><button type="button" onClick={logout} className="h-11 border border-danger px-4 text-sm font-semibold text-danger hover:bg-danger-soft">Đăng xuất</button></section>;
}
