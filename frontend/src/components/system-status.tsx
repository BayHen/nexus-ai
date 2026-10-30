"use client";

import { ArrowClockwiseIcon, CheckCircleIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { ErrorState } from "@/components/states/error-state";
import { LoadingState } from "@/components/states/loading-state";
import { ApiError, toUserMessage } from "@/lib/api/errors";
import { apiClient } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

type RequestState =
  | { status: "loading" }
  | { status: "success"; data: HealthResponse }
  | { status: "error"; message: string };

async function fetchSystemStatus(): Promise<RequestState> {
  try {
    const data = await apiClient.get<HealthResponse>("/api/backend/health");
    return { status: "success", data };
  } catch (error) {
    return {
      status: "error",
      message: toUserMessage(error instanceof ApiError ? error : new ApiError("unknown", 500)),
    };
  }
}

export function SystemStatus() {
  const [state, setState] = useState<RequestState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    void fetchSystemStatus().then((nextState) => {
      if (active) {
        setState(nextState);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const refresh = () => {
    setState({ status: "loading" });
    void fetchSystemStatus().then(setState);
  };

  if (state.status === "loading") {
    return <LoadingState label="Đang kiểm tra kết nối backend" />;
  }

  if (state.status === "error") {
    return (
      <ErrorState
        title="Backend chưa sẵn sàng"
        description={state.message}
        actionLabel="Kiểm tra lại"
        onAction={refresh}
      />
    );
  }

  return (
    <div className="border border-accent/25 bg-panel">
      <div className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <CheckCircleIcon aria-hidden="true" size={28} weight="fill" className="text-accent" />
          <div>
            <p className="font-semibold text-ink">FastAPI đã sẵn sàng</p>
            <p className="mt-1 text-sm leading-6 text-muted">
              Health contract trả về trạng thái {state.data.status}.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="inline-flex w-fit items-center gap-2 border border-line px-3 py-2 text-sm font-semibold text-ink hover:bg-canvas"
        >
          <ArrowClockwiseIcon size={16} weight="bold" />
          Làm mới
        </button>
      </div>
      <dl className="grid gap-px border-t border-line bg-line sm:grid-cols-2">
        {Object.entries(state.data.checks ?? {}).map(([name, value]) => (
          <div key={name} className="flex items-center justify-between bg-panel px-6 py-4">
            <dt className="font-mono text-xs uppercase text-muted">{name}</dt>
            <dd className="text-sm font-semibold text-accent">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
