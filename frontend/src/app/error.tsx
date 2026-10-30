"use client";

import { ErrorState } from "@/components/states/error-state";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-canvas p-6">
      <ErrorState
        title="Không thể hiển thị dashboard"
        description="Đã xảy ra lỗi khi dựng giao diện. Hãy thử tải lại phần này."
        actionLabel="Thử lại"
        onAction={reset}
      />
    </div>
  );
}
