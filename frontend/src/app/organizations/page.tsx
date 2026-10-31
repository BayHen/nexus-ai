import { AppShell } from "@/components/layout/app-shell";
import { OrganizationSelector } from "@/components/organizations/organization-selector";
import { PageHeader } from "@/components/ui/page-header";
export default function OrganizationsPage() { return <AppShell><main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6 lg:px-8"><PageHeader eyebrow="Workspace" title="Chọn tổ chức" description="Mọi dữ liệu sau đây sẽ được giới hạn theo active tenant do backend xác lập." /><OrganizationSelector /></main></AppShell>; }
