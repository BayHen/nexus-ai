import { TrayIcon } from "@phosphor-icons/react/ssr";

type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex min-h-52 flex-col justify-between border border-line bg-panel p-6">
      <TrayIcon aria-hidden="true" size={24} className="text-muted" />
      <div className="mt-10">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <p className="mt-2 max-w-sm text-sm leading-6 text-muted">{description}</p>
      </div>
    </div>
  );
}
