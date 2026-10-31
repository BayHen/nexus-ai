import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { ResourceTable, type Column } from "@/components/data/resource-table";
import { PageHeader } from "@/components/ui/page-header";

export function EntityPage<T>({ eyebrow, title, description, endpoint, columns, searchLabel, searchable, action, filter }: { eyebrow: string; title: string; description: string; endpoint: string; columns: Column<T>[]; searchLabel?: string; searchable?: boolean; action?: ReactNode; filter?: { name: string; label: string; options: { value: string; label: string }[] } }) {
  return <AppShell><main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8"><PageHeader eyebrow={eyebrow} title={title} description={description} action={action} /><ResourceTable endpoint={endpoint} columns={columns} searchLabel={searchLabel} searchable={searchable} filter={filter} /></main></AppShell>;
}
