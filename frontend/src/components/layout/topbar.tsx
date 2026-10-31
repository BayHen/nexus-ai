"use client";

import { ListIcon } from "@phosphor-icons/react";

export function Topbar({ onOpenNavigation, organizationName }: { onOpenNavigation: () => void; organizationName: string }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-line bg-panel/95 px-4 backdrop-blur sm:px-6 lg:px-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Mở menu điều hướng"
          className="grid size-9 place-items-center text-ink hover:bg-canvas lg:hidden"
          onClick={onOpenNavigation}
        >
          <ListIcon size={21} weight="bold" />
        </button>
        <div>
          <p className="text-xs text-muted">Workspace</p>
          <p className="max-w-[180px] truncate text-sm font-semibold sm:max-w-sm">{organizationName}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <a href="/organizations" className="hidden text-xs font-medium text-accent hover:underline sm:inline">Đổi tổ chức</a>
        <span className="border border-accent/25 bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent">
          Development
        </span>
      </div>
    </header>
  );
}
