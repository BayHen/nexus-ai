import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
export default function AnalyticsPage() { return <AppShell><main className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6 lg:px-8"><PageHeader eyebrow="Intelligence" title="Phân tích kinh doanh" description="Revenue recognition và refund được tính từ nguồn order/payment thật phía server." /><AnalyticsDashboard /></main></AppShell>; }
