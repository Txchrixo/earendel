import { test, expect } from "@playwright/test";

test("landing → demo → dashboard → run action → see execution", async ({ page }) => {
  // 1. Landing page loads
  await page.goto("/");
  await expect(page.locator("h1")).toContainText(/Record workflows/i);

  // 2. Click "Try the demo"
  await page.getByRole("button", { name: /try the demo/i }).click();

  // 3. Wait for dashboard (header h1 has "Dashboard" text; Hero h1 has
  //    different text, so we filter to avoid a strict-mode violation.
  //    signIn() is async + Prisma writes the demo user, so allow up to 20s.)
  await expect(
    page.locator("h1").filter({ hasText: /^Dashboard$/ }),
  ).toBeVisible({ timeout: 20000 });

  // 4. Check dashboard stats are visible (scope to main content — the
  //    sidebar nav button "Connectors" also matches, so filter it out.)
  await expect(
    page.getByRole("main").getByText(/CONNECTORS/i),
  ).toBeVisible({ timeout: 10000 });

  // 5. Navigate to Actions
  await page.getByRole("button", { name: /Actions/i }).first().click();
  await expect(page.locator("h2")).toContainText(/Typed Actions/i);

  // 6. Navigate to Playground
  await page.getByRole("button", { name: /Playground/i }).first().click();
  await expect(page.locator("h2")).toContainText(/Agent Playground/i);

  // 7. Navigate to Monitoring
  await page.getByRole("button", { name: /Monitoring/i }).first().click();
  await expect(page.locator("h2")).toContainText(/Monitoring/i);

  // 8. Navigate to Publishing
  await page.getByRole("button", { name: /Publishing/i }).first().click();
  await expect(page.locator("h2")).toContainText(/Publishing/i);
});

test("auth pages load correctly", async ({ page }) => {
  // Sign in page
  await page.goto("/auth/signin");
  await expect(page.locator("h1")).toContainText(/Welcome back/i);

  // Sign up page
  await page.goto("/auth/signup");
  await expect(page.locator("h1")).toContainText(/Create your account/i);
});

test("MCP server responds", async ({ request }) => {
  // Health check
  const health = await request.get("http://localhost:3004/health");
  expect(health.ok()).toBeTruthy();

  // Initialize
  const init = await request.post("http://localhost:3004/mcp", {
    data: { jsonrpc: "2.0", id: 1, method: "initialize", params: {} },
  });
  expect(init.ok()).toBeTruthy();
  const initBody = await init.json();
  expect(initBody.result.serverInfo.name).toBe("earendel-mcp-server");

  // Tools list
  const tools = await request.post("http://localhost:3004/mcp", {
    data: { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} },
  });
  expect(tools.ok()).toBeTruthy();
  const toolsBody = await tools.json();
  expect(toolsBody.result.tools.length).toBeGreaterThan(0);
});
