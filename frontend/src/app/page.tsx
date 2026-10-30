import { AppShell } from "@/components/layout/app-shell";
import { EmptyState } from "@/components/states/empty-state";
import { SystemStatus } from "@/components/system-status";

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <header className="mb-8 flex flex-col gap-4 border-b border-line pb-7 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="mb-2 font-mono text-xs font-semibold uppercase tracking-[0.16em] text-accent">
              Demo workspace
            </p>
            <h1 className="max-w-3xl text-3xl font-semibold tracking-[-0.035em] text-ink sm:text-4xl">
              Nền tảng đã sẵn sàng cho các module nghiệp vụ.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted sm:text-base">
              Dashboard foundation kết nối trực tiếp với health contract của FastAPI. Không có chỉ số
              sản xuất hoặc dữ liệu khách hàng giả trong màn hình này.
            </p>
          </div>
          <div className="w-fit border border-line bg-panel px-3 py-2 font-mono text-xs text-muted">
            ENV / LOCAL
          </div>
        </header>

        <main className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.75fr)]">
          <section aria-labelledby="system-status-title">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                  Runtime
                </p>
                <h2 id="system-status-title" className="mt-1 text-xl font-semibold tracking-tight">
                  Kết nối hệ thống
                </h2>
              </div>
              <span className="text-xs text-muted">Tự động làm mới khi tải trang</span>
            </div>
            <SystemStatus />
          </section>

          <section aria-labelledby="activity-title">
            <div className="mb-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                Activity
              </p>
              <h2 id="activity-title" className="mt-1 text-xl font-semibold tracking-tight">
                Hoạt động gần đây
              </h2>
            </div>
            <EmptyState
              title="Chưa có hoạt động"
              description="Sự kiện nghiệp vụ sẽ xuất hiện ở đây sau khi các module tương ứng được triển khai."
            />
          </section>
        </main>

        <section className="mt-10 border-t border-line pt-6" aria-labelledby="foundation-title">
          <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                Foundation
              </p>
              <h2 id="foundation-title" className="mt-1 text-xl font-semibold tracking-tight">
                Phạm vi hiện tại
              </h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                Các mục dưới đây phản ánh cấu trúc đã có trong repository, không phải dữ liệu vận hành.
              </p>
            </div>
            <dl className="grid gap-px overflow-hidden border border-line bg-line sm:grid-cols-3">
              {[
                ["API", "Versioned contract"],
                ["Database", "Migration baseline"],
                ["Frontend", "Dashboard shell"],
              ].map(([term, detail]) => (
                <div key={term} className="bg-panel p-5">
                  <dt className="font-mono text-xs text-muted">{term}</dt>
                  <dd className="mt-2 text-sm font-semibold text-ink">{detail}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
