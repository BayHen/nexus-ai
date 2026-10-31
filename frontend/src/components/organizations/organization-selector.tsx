"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BuildingsIcon } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api/client";
import type { Organization, PageResponse } from "@/lib/api/types";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";

export function OrganizationSelector() {
  const router = useRouter();
  const [data, setData] = useState<PageResponse<Organization> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiClient.get<PageResponse<Organization>>("/api/backend/organizations?page=1&page_size=100").then(setData).catch(() => setError("Không thể tải danh sách tổ chức từ backend.")); }, []);
  async function activate(organization: Organization) {
    try {
      await apiClient.post(`/api/backend/organizations/${organization.id}/activate`);
      sessionStorage.setItem("nexus_role", organization.role);
      sessionStorage.setItem("nexus_organization_name", organization.name);
      router.push("/");
    } catch { setError("Không thể kích hoạt tổ chức đã chọn."); }
  }
  if (error) return <ErrorState title="Không thể chọn tổ chức" description={error} />;
  if (!data) return <LoadingState label="Đang tải tổ chức" />;
  return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{data.items.map((organization) => <button key={organization.id} type="button" onClick={() => activate(organization)} className="group border border-line bg-panel p-5 text-left hover:border-accent"><BuildingsIcon size={25} className="text-accent" /><strong className="mt-5 block text-lg">{organization.name}</strong><span className="mt-1 block text-sm text-muted">{organization.slug}</span><span className="mt-5 inline-flex bg-canvas px-2 py-1 text-xs font-semibold capitalize text-muted">{organization.role}</span><span className="float-right mt-5 text-sm font-semibold text-accent opacity-0 transition-opacity group-hover:opacity-100">Mở →</span></button>)}</div>;
}
