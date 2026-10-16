import { expect, test } from "@playwright/test";

type HealthBody = {
  status: string;
  database: string;
  local_model: "configured" | "missing" | string;
};

test.describe("CareerOS copilot smoke", () => {
  test("register, health-aware model banner, profile, analyze error, empty history and analytics, sign out", async ({
    page,
    request,
  }) => {
    const healthResponse = await request.get("/health").catch(() => null);
    test.skip(!healthResponse || !healthResponse.ok(), "API is not running on E2E_BASE_URL");

    const health = (await healthResponse!.json()) as HealthBody;
    const modelConfigured = health.local_model === "configured";

    const email = `slice9-${Date.now()}@example.com`;
    await page.goto("/login");
    await page.getByRole("button", { name: "Need an account?" }).click();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("slice9-pass-1");
    await page.getByRole("button", { name: "Register", exact: true }).click();
    await expect(page.getByRole("heading", { name: /analyze a resume/i })).toBeVisible();

    if (modelConfigured) {
      await expect(page.getByText(/local model: not configured/i)).not.toBeVisible();
      await expect(page.getByText(/local model file is present/i)).toBeVisible();
    } else {
      await expect(page.getByText(/local model: not configured/i)).toBeVisible();
    }

    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Profile" }).click();
    await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
    await page.getByLabel("Default target role").fill("Software Developer");
    await page.getByLabel("Skills").fill("Python, APIs");
    await page.getByRole("button", { name: "Create profile" }).click();
    await expect(page.getByText("Profile saved.")).toBeVisible();

    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Analyze" }).click();
    const file = Buffer.from("Not a resume");
    await page.getByLabel(/resume \(pdf or docx/i).setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: file,
    });
    await page.getByLabel("Target role").fill("Software Developer");
    await page.getByLabel("Job description").fill("Required: Python and REST APIs");
    await page.getByRole("button", { name: "Run analysis" }).click();
    await expect(page.getByRole("alert")).toBeVisible();

    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "History" }).click();
    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
    await expect(page.getByText(/no analyses yet/i)).toBeVisible();

    await page.getByRole("navigation", { name: "Primary" }).getByRole("link", { name: "Analytics" }).click();
    await expect(page.getByRole("heading", { name: /your evidence, over time/i })).toBeVisible();
    await expect(page.getByText(/analytics stay empty/i)).toBeVisible();

    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });
});
