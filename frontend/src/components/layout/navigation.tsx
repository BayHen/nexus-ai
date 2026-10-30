"use client";

import {
  BrainIcon,
  BuildingsIcon,
  ChartDonutIcon,
  DatabaseIcon,
  HouseIcon,
  XIcon,
} from "@phosphor-icons/react";

const navigationItems = [
  { label: "Tổng quan", icon: HouseIcon, current: true },
  { label: "Tổ chức", icon: BuildingsIcon, current: false },
  { label: "Dữ liệu", icon: DatabaseIcon, current: false },
  { label: "AI workspace", icon: BrainIcon, current: false },
  { label: "Quan sát", icon: ChartDonutIcon, current: false },
];

type NavigationProps = {
  open: boolean;
  onClose: () => void;
};

export function Navigation({ open, onClose }: NavigationProps) {
  return (
    <>
      {open ? (
        <button
          type="button"
          aria-label="Đóng menu điều hướng"
          className="fixed inset-0 z-40 bg-ink/35 lg:hidden"
          onClick={onClose}
        />
      ) : null}
      <aside
        aria-label="Điều hướng chính"
        className={`fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-line bg-panel transition-transform duration-200 lg:sticky lg:top-0 lg:h-[100dvh] lg:w-auto lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-16 items-center justify-between border-b border-line px-5">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="grid size-8 place-items-center bg-ink font-mono text-xs font-bold text-white"
            >
              NX
            </span>
            <div>
              <p className="text-sm font-bold tracking-[-0.02em]">NEXUS AI</p>
              <p className="text-[11px] text-muted">Operations console</p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Đóng menu"
            className="grid size-9 place-items-center text-muted hover:bg-canvas hover:text-ink lg:hidden"
            onClick={onClose}
          >
            <XIcon size={18} weight="bold" />
          </button>
        </div>

        <div className="px-4 py-5">
          <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Demo workspace
          </p>
          <nav className="mt-3 space-y-1">
            {navigationItems.map(({ label, icon: Icon, current }) => (
              <a
                key={label}
                href={current ? "/" : "#planned-navigation"}
                aria-current={current ? "page" : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-colors ${
                  current
                    ? "bg-accent-soft text-accent"
                    : "text-muted hover:bg-canvas hover:text-ink"
                }`}
                onClick={onClose}
              >
                <Icon size={18} weight={current ? "fill" : "regular"} />
                {label}
                {!current ? <span className="ml-auto text-[10px] uppercase text-muted">Planned</span> : null}
              </a>
            ))}
          </nav>
        </div>

        <div className="mt-auto border-t border-line p-5">
          <p className="text-xs font-medium text-ink">Foundation phase</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Điều hướng chưa triển khai được đánh dấu Planned.
          </p>
        </div>
      </aside>
    </>
  );
}
