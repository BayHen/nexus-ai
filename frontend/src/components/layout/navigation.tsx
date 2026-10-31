"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BuildingsIcon, ChartLineUpIcon, ChatCircleDotsIcon, CreditCardIcon, GearIcon, HouseIcon, PackageIcon, ShoppingCartIcon, StackIcon, UsersIcon, XIcon } from "@phosphor-icons/react";
import type { Role } from "@/lib/api/types";

const items = [
  { label: "Tổng quan", href: "/", icon: HouseIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Tổ chức", href: "/organizations", icon: BuildingsIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Sản phẩm", href: "/products", icon: PackageIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Tồn kho", href: "/inventory", icon: StackIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Đơn hàng", href: "/orders", icon: ShoppingCartIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Thanh toán", href: "/payments", icon: CreditCardIcon, roles: ["owner", "admin", "manager", "staff"] },
  { label: "Phân tích", href: "/analytics", icon: ChartLineUpIcon, roles: ["owner", "admin", "manager"] },
  { label: "Trợ lý AI", href: "/assistant", icon: ChatCircleDotsIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
  { label: "Đội ngũ", href: "/team", icon: UsersIcon, roles: ["owner", "admin", "manager"] },
  { label: "Tài khoản", href: "/settings", icon: GearIcon, roles: ["owner", "admin", "manager", "staff", "viewer"] },
] satisfies { label: string; href: string; icon: typeof HouseIcon; roles: Role[] }[];

export function Navigation({ open, onClose, role }: { open: boolean; onClose: () => void; role: Role }) {
  const pathname = usePathname();
  return <>
    {open ? <button type="button" aria-label="Đóng menu điều hướng" className="fixed inset-0 z-40 bg-ink/35 lg:hidden" onClick={onClose} /> : null}
    <aside aria-label="Điều hướng chính" className={`fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-line bg-panel transition-transform lg:sticky lg:top-0 lg:h-[100dvh] lg:w-auto lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex h-16 items-center justify-between border-b border-line px-5"><Link href="/" className="flex items-center gap-3"><span className="grid size-8 place-items-center bg-ink font-mono text-xs font-bold text-white">NX</span><span><strong className="block text-sm">NEXUS AI</strong><small className="text-muted">Business console</small></span></Link><button type="button" aria-label="Đóng menu" className="grid size-9 place-items-center lg:hidden" onClick={onClose}><XIcon size={18} /></button></div>
      <nav className="space-y-1 overflow-y-auto p-4">{items.filter((item) => item.roles.includes(role)).map(({ label, href, icon: Icon }) => { const current = pathname === href; return <Link key={href} href={href} aria-current={current ? "page" : undefined} onClick={onClose} className={`flex items-center gap-3 px-3 py-2.5 text-sm font-medium ${current ? "bg-accent-soft text-accent" : "text-muted hover:bg-canvas hover:text-ink"}`}><Icon size={18} weight={current ? "fill" : "regular"} />{label}</Link>; })}</nav>
      <div className="mt-auto border-t border-line p-5"><p className="text-[11px] uppercase tracking-wider text-muted">Vai trò hiện tại</p><p className="mt-1 text-sm font-semibold capitalize">{role}</p></div>
    </aside>
  </>;
}
