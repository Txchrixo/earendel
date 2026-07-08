import { test, expect } from "@playwright/test";

const MCP_URL = process.env.MCP_URL || "http://localhost:3004";

test("landing → demo → dashboard → navigate views", async ({ page }) => {
  // 1. Landing page loads
  await page.goto("/");
  await expect(page.locator("h1")).toContainText(/Record workflows/i, { timeout: 15000 });

  // 2. Click "Try the demo"
  await page.getByRole("button", { name: /try the demo/i }).click();

  // 3. Wait for dashboard
  await expect(
    page.locator("h1").filter({ hasText: /^Dashboard$/ }),
  ).toBeVisible({ timeout: 30000 });

  // 4. Check dashboard stats
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

test("backend API responds", async ({ request }) => {
  // Health check on backend (port 8001)
  const health = await request.get(
    "http://localhost:8001/api/v1/healthz?XTransformPort=8001"
  );
  expect(health.ok()).toBeTruthy();
  const body = await health.json();
  expect(body.status).toBe("alive");
});
