export function LoadingState({ label = "Đang tải" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="border border-line bg-panel p-6">
      <div className="h-2 w-24 animate-pulse bg-line" />
      <div className="mt-5 h-5 w-48 animate-pulse bg-line" />
      <div className="mt-3 h-3 max-w-md animate-pulse bg-line/70" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
