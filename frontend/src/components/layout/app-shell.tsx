"use client";

import type { ReactNode } from "react";
import { useState } from "react";

import { Navigation } from "@/components/layout/navigation";
import { Topbar } from "@/components/layout/topbar";
import { useWorkspace } from "@/hooks/use-workspace";

export function AppShell({ children }: { children: ReactNode }) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const workspace = useWorkspace();

  return (
    <div className="min-h-[100dvh] bg-canvas lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      <Navigation open={navigationOpen} onClose={() => setNavigationOpen(false)} role={workspace.role} />
      <div className="min-w-0">
        <Topbar onOpenNavigation={() => setNavigationOpen(true)} organizationName={workspace.name} />
        {children}
      </div>
    </div>
  );
}
