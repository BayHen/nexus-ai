"use client";

import { WarningCircleIcon } from "@phosphor-icons/react";

type ErrorStateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function ErrorState({ title, description, actionLabel, onAction }: ErrorStateProps) {
  return (
    <div role="alert" className="border border-danger/25 bg-danger-soft p-6">
      <WarningCircleIcon aria-hidden="true" size={24} className="text-danger" weight="fill" />
      <h3 className="mt-6 text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">{description}</p>
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="mt-5 bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-ink/85"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
