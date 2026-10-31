import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AssistantWorkspace } from "@/components/assistant/assistant-workspace";

const agentResponse = { run_id: "run-1", status: "completed", selected_tool: "search_knowledge_base", answer: "Chính sách hoàn tiền là 30 ngày.", citations: [{ document_id: "doc-1", document_name: "policy.md", chunk_ordinal: 0, excerpt: "Hoàn tiền trong 30 ngày", distance: 0.1 }], transitions: ["authorize", "plan", "execute_tool", "compose_answer"] };

describe("AssistantWorkspace", () => {
  it("renders a safe answer, tool status, and citations", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "message-1" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("knowledge/documents")) return new Response(JSON.stringify([]), { status: 200 });
      return new Response(JSON.stringify(agentResponse), { status: 200 });
    });
    render(<AssistantWorkspace />);
    fireEvent.change(screen.getByLabelText("Câu hỏi cho AI Assistant"), { target: { value: "Summarize our authorized business documents." } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));
    expect(await screen.findByText("Chính sách hoàn tiền là 30 ngày.")).toBeInTheDocument();
    expect(screen.getByText("Tool: search_knowledge_base")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Nguồn trích dẫn" })).toHaveTextContent("policy.md");
  });

  it("shows an explicit permission error without fabricated content", async () => {
    vi.stubGlobal("crypto", { randomUUID: () => "message-2" });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).includes("knowledge/documents") ? new Response(JSON.stringify([]), { status: 200 }) : new Response(JSON.stringify({ error: { code: "tenant_access_denied", message: "denied" } }), { status: 403 }));
    render(<AssistantWorkspace />);
    fireEvent.change(screen.getByLabelText("Câu hỏi cho AI Assistant"), { target: { value: "What was our revenue this month?" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi câu hỏi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("không có quyền");
    await waitFor(() => expect(screen.queryByText(/Net revenue was/)).not.toBeInTheDocument());
  });
});
