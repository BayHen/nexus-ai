import { LoadingState } from "@/components/states/loading-state";

export default function Loading() {
  return (
    <div className="min-h-[100dvh] bg-canvas p-6">
      <div className="mx-auto max-w-[1440px]">
        <LoadingState label="Đang tải NEXUS AI Console" />
      </div>
    </div>
  );
}
