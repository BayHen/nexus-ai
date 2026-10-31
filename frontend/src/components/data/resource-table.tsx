"use client";

import { useEffect, useState } from "react";
import { MagnifyingGlassIcon } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api/client";
import { ApiError, toUserMessage } from "@/lib/api/errors";
import type { PageResponse } from "@/lib/api/types";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";

export type Column<T> = { key: string; label: string; render: (item: T) => React.ReactNode };

type Filter = { name: string; label: string; options: { value: string; label: string }[] };

export function ResourceTable<T>({ endpoint, columns, searchLabel = "Tìm kiếm", searchable = true, filter }: { endpoint: string; columns: Column<T>[]; searchLabel?: string; searchable?: boolean; filter?: Filter }) {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [filterValue, setFilterValue] = useState("");
  const [data, setData] = useState<PageResponse<T> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const filterName = filter?.name;

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams({ page: String(page), page_size: "10" });
    if (submittedQuery) params.set("query", submittedQuery);
    if (filterValue && filterName) params.set(filterName, filterValue);
    apiClient.get<PageResponse<T>>(`${endpoint}?${params}`).then((value) => active && setData(value)).catch((reason: unknown) => {
      if (active) setError(reason instanceof ApiError ? toUserMessage(reason) : "Không thể tải dữ liệu.");
    }).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [endpoint, filterName, filterValue, page, submittedQuery]);

  if (loading) return <LoadingState label="Đang tải dữ liệu từ backend" />;
  if (error) return <ErrorState title="Không thể tải dữ liệu" description={error} />;
  return (
    <section className="border border-line bg-panel">
      <form className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row" onSubmit={(event) => { event.preventDefault(); setLoading(true); setError(null); setPage(1); setSubmittedQuery(query.trim()); }}>
        {searchable ? <label className="relative min-w-0 flex-1">
          <span className="sr-only">{searchLabel}</span>
          <MagnifyingGlassIcon aria-hidden className="absolute left-3 top-3 text-muted" size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="h-11 w-full border border-line bg-white pl-10 pr-3 text-sm" placeholder={searchLabel} />
        </label> : <div className="flex-1" />}
        {filter ? <label><span className="sr-only">{filter.label}</span><select className="h-11 border border-line bg-white px-3 text-sm" value={filterValue} onChange={(event) => { setLoading(true); setError(null); setPage(1); setFilterValue(event.target.value); }}><option value="">{filter.label}: Tất cả</option>{filter.options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label> : null}
        {searchable ? <button className="h-11 bg-ink px-5 text-sm font-semibold text-white hover:bg-accent" type="submit">Tìm kiếm</button> : null}
      </form>
      {!data?.items.length ? <div className="p-5"><EmptyState title="Không có dữ liệu" description="Backend không trả về bản ghi phù hợp với bộ lọc hiện tại." /></div> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead className="bg-canvas text-xs uppercase tracking-wider text-muted"><tr>{columns.map((column) => <th className="px-5 py-3 font-semibold" key={column.key}>{column.label}</th>)}</tr></thead>
            <tbody>{data.items.map((item, index) => <tr className="border-t border-line hover:bg-canvas/60" key={index}>{columns.map((column) => <td className="px-5 py-4" key={column.key}>{column.render(item)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
      <footer className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-muted">
        <span>{data?.total ?? 0} bản ghi</span>
        <div className="flex items-center gap-2"><button type="button" disabled={page <= 1} onClick={() => { setLoading(true); setPage((value) => value - 1); }} className="border border-line px-3 py-1.5 disabled:opacity-40">Trước</button><span>Trang {page}</span><button type="button" disabled={!data || page * data.page_size >= data.total} onClick={() => { setLoading(true); setPage((value) => value + 1); }} className="border border-line px-3 py-1.5 disabled:opacity-40">Sau</button></div>
      </footer>
    </section>
  );
}
