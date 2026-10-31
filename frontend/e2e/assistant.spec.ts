import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/backend/knowledge/documents*", async (route) => {
    if (route.request().method() === "POST") return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "doc-2", filename: "guide.md", media_type: "text/markdown", file_size: 20, visibility: "organization", status: "ready", chunk_count: 1, embedding_model: "test", created_at: "2026-10-31T00:00:00Z" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ id: "doc-1", filename: "policy.md", media_type: "text/markdown", file_size: 100, visibility: "organization", status: "ready", chunk_count: 3, embedding_model: "test", created_at: "2026-10-31T00:00:00Z" }]) });
  });
  await page.route("**/api/backend/agent/ask*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ run_id: "run-1", status: "completed", selected_tool: "search_knowledge_base", answer: "Chính sách cho phép hoàn tiền trong 30 ngày.", citations: [{ document_id: "doc-1", document_name: "policy.md", chunk_ordinal: 0, excerpt: "Hoàn tiền trong 30 ngày.", distance: 0.1 }], transitions: ["authorize", "plan", "execute_tool", "compose_answer"] }) }));
});

test("asks the tenant-scoped assistant and shows evidence", async ({ page }) => {
  const initialResponse = await page.goto("/assistant");
  expect(initialResponse?.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  await page.evaluate(() => {
    sessionStorage.setItem("nexus_role", "owner");
    sessionStorage.setItem("nexus_organization_id", "org-1");
    sessionStorage.setItem("nexus_organization_name", "NEXUS Demo");
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Trợ lý kinh doanh" })).toBeVisible();
  await expect(page.getByText("policy.md").first()).toBeVisible();
  await page.getByLabel("Câu hỏi cho AI Assistant").fill("Summarize our authorized business documents.");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  await expect(page.getByText("Chính sách cho phép hoàn tiền trong 30 ngày.")).toBeVisible();
  await expect(page.getByText("Tool: search_knowledge_base")).toBeVisible();
  await expect(page.getByRole("list", { name: "Nguồn trích dẫn" })).toContainText("policy.md");
});
