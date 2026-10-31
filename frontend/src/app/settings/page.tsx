import { AppShell } from "@/components/layout/app-shell";
import { AccountPanel } from "@/components/account/account-panel";
import { FeatureUnavailable } from "@/components/ui/feature-unavailable";
import { PageHeader } from "@/components/ui/page-header";
export default function SettingsPage() { return <AppShell><main className="mx-auto max-w-[1000px] px-4 py-8 sm:px-6 lg:px-8"><PageHeader eyebrow="Personal" title="Cài đặt tài khoản" description="Thông tin nhận dạng đến từ authenticated user profile." /><AccountPanel /><FeatureUnavailable title="Account update API chưa được triển khai" description="Backend có endpoint đọc /auth/me nhưng chưa có contract cập nhật email, mật khẩu hoặc hồ sơ. Không hiển thị form không thể lưu." /></main></AppShell>; }
