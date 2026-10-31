"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpIcon, CheckCircleIcon, FileTextIcon, RobotIcon, UploadSimpleIcon } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AgentPeriod, AgentResponse, KnowledgeDocument } from "@/lib/api/types";

type Message = { id: string; role: "user" | "assistant"; text: string; response?: AgentResponse };
const examples = ["What was our revenue this month?", "Which products sold the most?", "Which products are running low?", "Summarize our authorized business documents."];

function historyKey() {
  return `nexus_ai_history:${sessionStorage.getItem("nexus_organization_id") ?? "active"}`;
}

export function AssistantWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [periodA, setPeriodA] = useState<AgentPeriod>({ date_from: "", date_to: "" });
  const [periodB, setPeriodB] = useState<AgentPeriod>({ date_from: "", date_to: "" });
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { void Promise.resolve().then(() => { try { setMessages(JSON.parse(sessionStorage.getItem(historyKey()) ?? "[]") as Message[]); } catch { setMessages([]); } }); }, []);
  useEffect(() => { if (messages.length) sessionStorage.setItem(historyKey(), JSON.stringify(messages.slice(-30))); if (typeof endRef.current?.scrollIntoView === "function") endRef.current.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  const comparing = useMemo(() => /compare|so sánh/i.test(question), [question]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const clean = question.trim();
    if (clean.length < 3 || pending) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", text: clean };
    setMessages((current) => [...current, userMessage]); setQuestion(""); setError(null); setPending(true);
    try {
      const body: Record<string, unknown> = { question: clean, currency: "USD" };
      if (comparing && Object.values(periodA).every(Boolean) && Object.values(periodB).every(Boolean)) { body.period_a = periodA; body.period_b = periodB; }
      const response = await apiClient.post<AgentResponse>("/api/backend/agent/ask", body);
      setMessages((current) => [...current, { id: response.run_id, role: "assistant", text: response.answer, response }]);
    } catch (cause) {
      const message = cause instanceof ApiError && cause.status === 403 ? "Bạn không có quyền sử dụng AI Assistant trong tổ chức này." : "AI Assistant không thể hoàn thành yêu cầu. Không có dữ liệu giả được hiển thị.";
      setError(message);
    } finally { setPending(false); }
  }

  return <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
    <section className="flex min-h-[680px] flex-col border border-line bg-panel" aria-label="Hội thoại AI">
      <header className="border-b border-line px-5 py-4"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center bg-accent-soft text-accent"><RobotIcon size={20} weight="fill" /></span><div><h2 className="font-semibold">NEXUS Business Assistant</h2><p className="text-xs text-muted">Chỉ đọc · Dữ liệu thuộc organization hiện tại</p></div></div></header>
      <div className="flex-1 space-y-5 overflow-y-auto p-5" aria-live="polite">
        {!messages.length ? <div className="mx-auto max-w-xl py-16 text-center"><RobotIcon className="mx-auto text-accent" size={34} /><h3 className="mt-5 text-xl font-semibold">Bạn muốn tìm hiểu điều gì?</h3><p className="mt-2 text-sm leading-6 text-muted">Assistant chỉ dùng các analytics và tài liệu mà tài khoản hiện tại được phép truy cập.</p><div className="mt-7 grid gap-2 sm:grid-cols-2">{examples.map((item) => <button key={item} type="button" onClick={() => setQuestion(item)} className="border border-line p-3 text-left text-sm hover:border-accent">{item}</button>)}</div></div> : null}
        {messages.map((message) => <article key={message.id} className={message.role === "user" ? "ml-auto max-w-2xl bg-ink px-4 py-3 text-sm text-white" : "max-w-3xl border-l-2 border-accent bg-accent-soft/50 px-4 py-4 text-sm"}><p className="whitespace-pre-wrap leading-6">{message.text}</p>{message.response ? <AgentResult response={message.response} /> : null}</article>)}
        {pending ? <div role="status" className="flex items-center gap-3 text-sm text-muted"><span className="size-2 animate-pulse rounded-full bg-accent" />Đang xác thực và thực thi công cụ…</div> : null}
        {error ? <p role="alert" className="border border-danger/25 bg-danger-soft p-4 text-sm text-danger">{error}</p> : null}<div ref={endRef} />
      </div>
      <form onSubmit={submit} className="border-t border-line p-4">
        {comparing ? <div className="mb-3 grid gap-3 border border-line bg-canvas p-3 sm:grid-cols-2"><PeriodFields label="Giai đoạn A" value={periodA} onChange={setPeriodA} /><PeriodFields label="Giai đoạn B" value={periodB} onChange={setPeriodB} /></div> : null}
        <div className="flex gap-2"><label className="sr-only" htmlFor="assistant-question">Câu hỏi cho AI Assistant</label><textarea id="assistant-question" rows={2} maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Hỏi về doanh thu, sản phẩm, tồn kho hoặc tài liệu…" className="min-h-14 flex-1 resize-none border border-line px-4 py-3 text-sm" /><button type="submit" disabled={pending || question.trim().length < 3} aria-label="Gửi câu hỏi" className="grid w-14 place-items-center bg-accent text-white disabled:opacity-40"><ArrowUpIcon size={20} weight="bold" /></button></div>
        <p className="mt-2 text-xs text-muted">AI có thể sai. Kiểm tra số liệu và citations trước khi đưa ra quyết định.</p>
      </form>
    </section>
    <DocumentLibrary />
  </div>;
}

function AgentResult({ response }: { response: AgentResponse }) {
  return <div className="mt-4 border-t border-accent/20 pt-3"><div className="flex flex-wrap gap-2 text-xs"><span className="bg-panel px-2 py-1 font-semibold">{response.status === "completed" ? "Hoàn thành" : response.status}</span>{response.selected_tool ? <span className="bg-panel px-2 py-1 font-mono">Tool: {response.selected_tool}</span> : null}<span className="bg-panel px-2 py-1">{response.transitions.length} bước</span></div>{response.citations.length ? <ol className="mt-3 space-y-2" aria-label="Nguồn trích dẫn">{response.citations.map((citation) => <li key={`${citation.document_id}-${citation.chunk_ordinal}`} className="border border-line bg-panel p-3"><div className="flex items-center gap-2 text-xs font-semibold"><FileTextIcon />{citation.document_name} · đoạn {citation.chunk_ordinal + 1}</div><blockquote className="mt-2 text-xs leading-5 text-muted">{citation.excerpt}</blockquote></li>)}</ol> : response.selected_tool === "search_knowledge_base" ? <p className="mt-3 text-xs text-muted">Không có nguồn đủ độ tin cậy để trích dẫn.</p> : null}</div>;
}

function PeriodFields({ label, value, onChange }: { label: string; value: AgentPeriod; onChange: (value: AgentPeriod) => void }) {
  return <fieldset><legend className="mb-2 text-xs font-semibold">{label}</legend><div className="flex gap-2"><input aria-label={`${label} từ ngày`} type="date" value={value.date_from} onChange={(e) => onChange({ ...value, date_from: e.target.value })} className="min-w-0 flex-1 border border-line p-2 text-xs" /><input aria-label={`${label} đến ngày`} type="date" value={value.date_to} onChange={(e) => onChange({ ...value, date_to: e.target.value })} className="min-w-0 flex-1 border border-line p-2 text-xs" /></div></fieldset>;
}

function DocumentLibrary() {
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null); const [error, setError] = useState<string | null>(null); const [uploading, setUploading] = useState(false);
  const load = () => apiClient.get<KnowledgeDocument[]>("/api/backend/knowledge/documents").then(setDocuments).catch(() => setError("Không thể tải tài liệu hoặc bạn không có quyền knowledge:read."));
  useEffect(() => { void load(); }, []);
  async function upload(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = event.currentTarget; const file = new FormData(form).get("file"); if (!(file instanceof File) || !file.size) return; setUploading(true); setError(null); const body = new FormData(); body.append("file", file); body.append("visibility", "organization"); try { await apiClient.post<KnowledgeDocument>("/api/backend/knowledge/documents", body); form.reset(); await load(); } catch { setError("Upload thất bại. Chỉ chấp nhận PDF, TXT, Markdown trong giới hạn backend."); } finally { setUploading(false); } }
  return <aside className="border border-line bg-panel p-5" aria-label="Kho tài liệu"><div className="flex items-center justify-between"><div><h2 className="font-semibold">Knowledge Base</h2><p className="mt-1 text-xs text-muted">Tài liệu được index theo tenant</p></div><FileTextIcon size={22} className="text-accent" /></div><form onSubmit={upload} className="mt-5 border border-dashed border-line p-4"><label className="block text-sm font-semibold" htmlFor="knowledge-file">Tải tài liệu</label><input id="knowledge-file" name="file" type="file" accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf" className="mt-3 block w-full text-xs" required /><button disabled={uploading} className="mt-4 flex h-10 w-full items-center justify-center gap-2 bg-ink text-sm font-semibold text-white disabled:opacity-50"><UploadSimpleIcon />{uploading ? "Đang index…" : "Upload và index"}</button></form>{error ? <p role="alert" className="mt-4 bg-danger-soft p-3 text-xs text-danger">{error}</p> : null}<div className="mt-5 space-y-2">{documents?.map((document) => <div key={document.id} className="border border-line p-3"><div className="flex items-start gap-2"><CheckCircleIcon className={document.status === "ready" ? "text-accent" : "text-danger"} weight="fill" /><div className="min-w-0"><p className="truncate text-sm font-semibold">{document.filename}</p><p className="mt-1 text-xs text-muted">{document.status === "ready" ? `${document.chunk_count} chunks · đã index` : "Index thất bại"}</p><p className="mt-1 text-[11px] text-muted">{document.visibility === "private" ? "Riêng tư" : "Toàn organization"}</p></div></div></div>)}{documents?.length === 0 ? <p className="text-sm text-muted">Chưa có tài liệu được phép truy cập.</p> : null}{documents === null && !error ? <p role="status" className="text-sm text-muted">Đang tải tài liệu…</p> : null}</div></aside>;
}
