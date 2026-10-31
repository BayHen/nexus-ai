export type HealthStatus = "alive" | "ready" | "not_ready";

export type HealthResponse = {
  status: HealthStatus;
  checks: Record<string, "up" | "down"> | null;
};

export type ApiErrorPayload = {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
};

export type Role = "owner" | "admin" | "manager" | "staff" | "viewer";
export type PageResponse<T> = { items: T[]; page: number; page_size: number; total: number };
export type Organization = { id: string; name: string; slug: string; role: Role; created_at: string };
export type UserProfile = { id: string; email: string; is_active: boolean; created_at: string };
export type Product = { id: string; sku: string; name: string; price: string; status: "draft" | "active" | "archived"; category_id: string | null; updated_at: string };
export type Stock = { branch_id: string; branch_name: string | null; product_id: string; product_name: string | null; product_sku: string | null; quantity: string; low_stock_threshold: string; is_low_stock: boolean; updated_at: string };
export type Order = { id: string; status: "draft" | "confirmed" | "completed" | "cancelled"; total_amount: string; items: unknown[]; created_at: string; updated_at: string };
export type Member = { organization_id: string; user_id: string; email: string; role: Role; status: "pending" | "active"; created_at: string };
export type AnalyticsSummary = { currency: string; total_revenue: string; gross_revenue: string; refunded_amount: string; order_count: number; average_order_value: string };
export type RevenueSeries = { currency: string; granularity: "day" | "month"; items: { period: string; revenue: string; order_count: number }[] };

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (!value || typeof value !== "object" || !("status" in value) || !("checks" in value)) {
    return false;
  }
  const statusIsValid = ["alive", "ready", "not_ready"].includes(String(value.status));
  const checksAreValid =
    value.checks === null ||
    (typeof value.checks === "object" &&
      Object.values(value.checks).every((check) => check === "up" || check === "down"));
  return statusIsValid && checksAreValid;
}
