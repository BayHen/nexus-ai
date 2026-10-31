import { AppShell } from "@/components/layout/app-shell";
import { FeatureUnavailable } from "@/components/ui/feature-unavailable";
import { PageHeader } from "@/components/ui/page-header";
export default function PaymentsPage() { return <AppShell><main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6 lg:px-8"><PageHeader eyebrow="Finance" title="Lịch sử thanh toán" description="Theo dõi payment intent và refund của active organization." /><FeatureUnavailable title="Payment list API chưa được triển khai" description="Backend hiện hỗ trợ đọc payment intent theo ID nhưng chưa có tenant-scoped collection endpoint. Dashboard không tạo dữ liệu thanh toán giả để lấp chỗ trống." /></main></AppShell>; }
