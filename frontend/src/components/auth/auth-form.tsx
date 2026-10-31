"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiClient } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Vui lòng nhập email hợp lệ.");
    if (password.length < 12) return setError("Mật khẩu phải có ít nhất 12 ký tự.");
    setSubmitting(true);
    try {
      await apiClient.post(`/api/backend/auth/${mode}`, { email, password });
      router.push("/organizations");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Không thể kết nối backend.");
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="grid min-h-[100dvh] lg:grid-cols-[0.9fr_1.1fr]">
    <section className="flex items-center bg-panel px-6 py-12 sm:px-12 lg:px-20"><div className="mx-auto w-full max-w-md"><Link href="/" className="font-mono text-sm font-bold tracking-wider">NX / NEXUS AI</Link><p className="mt-14 font-mono text-[11px] font-bold uppercase tracking-[0.16em] text-accent">Enterprise workspace</p><h1 className="mt-3 text-4xl font-semibold tracking-[-0.04em]">{isRegister ? "Tạo tài khoản" : "Đăng nhập"}</h1><p className="mt-3 text-sm leading-6 text-muted">{isRegister ? "Khởi tạo workspace an toàn cho tổ chức của bạn." : "Tiếp tục vào bảng điều hành doanh nghiệp."}</p>
      <form className="mt-9 space-y-5" onSubmit={submit} noValidate><label className="block"><span className="text-sm font-semibold">Email</span><input className="mt-2 h-12 w-full border border-line px-4 text-sm" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label className="block"><span className="text-sm font-semibold">Mật khẩu</span><input className="mt-2 h-12 w-full border border-line px-4 text-sm" type="password" autoComplete={isRegister ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} required /></label>{error ? <p role="alert" className="bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p> : null}<button disabled={submitting} className="h-12 w-full bg-ink font-semibold text-white hover:bg-accent disabled:opacity-60">{submitting ? "Đang xử lý…" : isRegister ? "Đăng ký" : "Đăng nhập"}</button></form>
      <p className="mt-6 text-sm text-muted">{isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <Link className="font-semibold text-accent hover:underline" href={isRegister ? "/login" : "/register"}>{isRegister ? "Đăng nhập" : "Đăng ký"}</Link></p></div></section>
    <aside className="hidden overflow-hidden bg-ink p-16 text-white lg:flex lg:flex-col lg:justify-between"><p className="font-mono text-xs uppercase tracking-[0.18em] text-white/55">Intelligence meets operations</p><blockquote className="max-w-xl text-4xl font-medium leading-tight tracking-[-0.035em]">Một điểm kiểm soát cho doanh thu, tồn kho, đơn hàng và tri thức doanh nghiệp.</blockquote><div className="grid grid-cols-3 gap-px bg-white/15"><span className="bg-ink p-4 text-xs text-white/65">Tenant-safe</span><span className="bg-ink p-4 text-xs text-white/65">Auditable</span><span className="bg-ink p-4 text-xs text-white/65">AI-ready</span></div></aside>
  </main>;
}
