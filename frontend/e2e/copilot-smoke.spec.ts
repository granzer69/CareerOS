import { expect, test } from "@playwright/test";

test.describe("CareerOS copilot smoke", () => {
  test("register, missing-model banner, analyze error, empty history, sign out", async ({
    page,
    request,
  }) => {
    const health = await request.get("/health").catch(() => null);
    test.skip(!health || !health.ok(), "API is not running on E2E_BASE_URL");

    const email = `slice7-${Date.now()}@example.com`;
    await page.goto("/login");
    await page.getByRole("button", { name: "Need an account?" }).click();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("slice7-pass-1");
    await page.getByRole("button", { name: "Register", exact: true }).click();
    await expect(page.getByRole("heading", { name: /analyze a resume/i })).toBeVisible();
    await expect(page.getByText(/local model: not configured/i)).toBeVisible();

    const file = Buffer.from("Not a resume");
    await page.getByLabel(/resume \(pdf or docx/i).setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: file,
    });
    await page.getByLabel("Target role").fill("Backend Engineer");
    await page.getByLabel("Job description").fill("Required: Python");
    await page.getByRole("button", { name: "Run analysis" }).click();
    await expect(page.getByRole("alert")).toBeVisible();

    await page.getByRole("link", { name: "History" }).click();
    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
    await expect(page.getByText(/no analyses yet/i)).toBeVisible();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
});
