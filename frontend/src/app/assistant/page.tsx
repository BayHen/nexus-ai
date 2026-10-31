import { AssistantWorkspace } from "@/components/assistant/assistant-workspace";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";

export default function AssistantPage() {
  return <AppShell><main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8"><PageHeader eyebrow="AI workspace" title="Trợ lý kinh doanh" description="Hỏi dữ liệu read-only, theo dõi tool execution và kiểm chứng câu trả lời bằng citations." /><AssistantWorkspace /></main></AppShell>;
}
