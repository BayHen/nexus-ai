import Link from "next/link";
import { ArrowUpRightIcon, ChartLineUpIcon, PackageIcon, ShoppingCartIcon, StackIcon } from "@phosphor-icons/react/dist/ssr";
import { AnalyticsDashboard } from "@/components/analytics/analytics-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";

const modules = [
  { href: "/products", title: "Sản phẩm", description: "Catalog, giá và trạng thái", icon: PackageIcon },
  { href: "/inventory", title: "Tồn kho", description: "Stock theo chi nhánh", icon: StackIcon },
  { href: "/orders", title: "Đơn hàng", description: "Draft đến completed", icon: ShoppingCartIcon },
  { href: "/analytics", title: "Phân tích", description: "Revenue và xu hướng", icon: ChartLineUpIcon },
];

export default function DashboardPage() {
  return <AppShell><main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
    <PageHeader eyebrow="Command center" title="Tổng quan doanh nghiệp" description="Chỉ số được đọc trực tiếp từ analytics API của active organization; lỗi backend sẽ được hiển thị thay vì dùng dữ liệu giả." action={<Link href="/analytics" className="inline-flex h-11 items-center gap-2 bg-ink px-4 text-sm font-semibold text-white hover:bg-accent">Xem phân tích <ArrowUpRightIcon /></Link>} />
    <AnalyticsDashboard />
    <section className="mt-8"><div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">Không gian vận hành</h2><span className="text-xs text-muted">Dữ liệu theo active tenant</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{modules.map(({ href, title, description, icon: Icon }) => <Link href={href} key={href} className="group border border-line bg-panel p-5 hover:border-accent"><Icon size={24} className="text-accent" /><strong className="mt-5 block">{title}</strong><span className="mt-1 block text-sm text-muted">{description}</span><ArrowUpRightIcon className="mt-5 text-muted group-hover:text-accent" /></Link>)}</div></section>
  </main></AppShell>;
}
