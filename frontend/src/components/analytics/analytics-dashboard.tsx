"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type { AnalyticsSummary, RevenueSeries } from "@/lib/api/types";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";

export function AnalyticsDashboard() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [series, setSeries] = useState<RevenueSeries | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { Promise.all([apiClient.get<AnalyticsSummary>("/api/backend/analytics/summary?currency=USD"), apiClient.get<RevenueSeries>("/api/backend/analytics/revenue?currency=USD&granularity=day")]).then(([a, b]) => { setSummary(a); setSeries(b); }).catch(() => setError(true)); }, []);
  if (error) return <ErrorState title="Không thể tải analytics" description="Backend trả lỗi hoặc tài khoản không có quyền audit:read." />;
  if (!summary || !series) return <LoadingState label="Đang tải analytics" />;
  const cards = [["Doanh thu thuần", summary.total_revenue], ["Đơn hoàn tất", String(summary.order_count)], ["Giá trị trung bình", summary.average_order_value], ["Đã hoàn tiền", summary.refunded_amount]];
  const max = Math.max(...series.items.map((item) => Number(item.revenue)), 1);
  return <><dl className="grid gap-px border border-line bg-line sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value]) => <div className="bg-panel p-5" key={label}><dt className="text-xs uppercase tracking-wider text-muted">{label}</dt><dd className="mt-3 text-2xl font-semibold">{label === "Đơn hoàn tất" ? value : new Intl.NumberFormat("vi-VN", { style: "currency", currency: summary.currency }).format(Number(value))}</dd></div>)}</dl><section className="mt-6 border border-line bg-panel p-5"><h2 className="font-semibold">Doanh thu theo ngày</h2>{series.items.length ? <div className="mt-6 flex h-52 items-end gap-2" aria-label="Biểu đồ doanh thu">{series.items.map((item) => <div key={item.period} className="group flex min-w-0 flex-1 flex-col justify-end"><span className="mb-2 hidden text-center text-[10px] text-muted group-hover:block">{item.revenue}</span><div className="min-h-1 bg-accent" style={{ height: `${Math.max((Number(item.revenue) / max) * 100, 2)}%` }} /><span className="mt-2 truncate text-center text-[10px] text-muted">{new Date(item.period).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })}</span></div>)}</div> : <p className="mt-5 text-sm text-muted">Không có doanh thu trong khoảng thời gian này.</p>}</section></>;
}
