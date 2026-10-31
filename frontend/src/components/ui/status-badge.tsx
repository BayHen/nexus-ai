export function StatusBadge({ value, tone = "neutral" }: { value: string; tone?: "neutral" | "success" | "warning" | "danger" }) {
  const styles = { neutral: "bg-canvas text-muted", success: "bg-accent-soft text-accent", warning: "bg-amber-50 text-amber-800", danger: "bg-danger-soft text-danger" };
  return <span className={`inline-flex px-2 py-1 text-xs font-semibold capitalize ${styles[tone]}`}>{value}</span>;
}
