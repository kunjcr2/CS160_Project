import { test, expect } from "./fixtures.js";
const demo = "http://127.0.0.1:5180";
const live = "http://127.0.0.1:5181";
const summary = "I need help using the appointment screen.";
async function openHelp(page) {
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await page.getByLabel("What do you need help with?", { exact: true }).fill(summary);
}
async function liveSession(page, role = "older_adult") {
  await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ json: { access_token: "request-test-token" } }));
  await page.route("**/api/v1/users/me", (route) => route.fulfill({ json: { id: "user-1", role, display_name: "Test user", timezone: "America/Los_Angeles" } }));
  await page.route("**/api/v1/notifications", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/assistance/queue", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/older-adults/user-1/medications", (route) => route.fulfill({ json: [{ id: "med-1", name: "Lisinopril", dosage: "10 mg", schedules: [] }] }));
}

test("help is reviewed before sharing, cancel keeps draft, and confirm enqueues just once", async ({ page }) => {
  await page.goto(demo); await openHelp(page);
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  await expect(page.getByText("REVIEW HELP REQUEST", { exact: true })).toBeVisible();
  await expect(page.getByText("No help requests yet.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveValue(summary);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveValue(summary);
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).evaluate((button) => { button.click(); button.click(); });
  const history = page.getByRole("region", { name: "Your help requests" });
  await expect(history.getByRole("listitem")).toHaveCount(1);
  await expect(history.getByText(summary, { exact: true })).toBeVisible();
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveValue("");
  await expect(page.getByText("Sample help request added to the demo queue. No real support agent was contacted.")).toBeVisible();
});

test("demo support lifecycle updates the older adult's request history", async ({ page }) => {
  await page.goto(demo); await openHelp(page);
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("region", { name: "Your help requests" }).getByRole("listitem")).toHaveCount(1);
  await page.getByRole("button", { name: "Preview support queue", exact: true }).click();
  await page.getByRole("button", { name: "View request from Margaret (sample)", exact: true }).click();
  const details = page.getByRole("region", { name: "Request details" });
  await expect(details.getByText(summary, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Take request", exact: true }).evaluate((button) => { button.click(); button.click(); });
  await expect(page.getByText("Sample request updated: In progress. No real handoff occurred.")).toBeVisible();
  await page.getByLabel("Queue status", { exact: true }).selectOption("in_progress");
  await page.getByRole("button", { name: "View request from Margaret (sample)", exact: true }).click();
  await page.getByRole("button", { name: "Mark resolved", exact: true }).click();
  await expect(page.getByText("No requests in this view.")).toBeVisible();
  await page.getByLabel("Queue status", { exact: true }).selectOption("resolved");
  await expect(page.getByRole("list", { name: "Queue requests" }).getByRole("listitem")).toHaveCount(1);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await expect(page.getByRole("region", { name: "Your help requests" }).getByText("Resolved", { exact: true })).toBeVisible();
});

test("support mutation failure blocks repeat changes until refresh; retry then succeeds", async ({ page }) => {
  await page.goto(demo);
  await page.getByRole("button", { name: "Preview support queue", exact: true }).click();
  await page.getByRole("button", { name: "View request from Alex (sample)", exact: true }).click();
  await page.getByText("Demo controls", { exact: true }).click();
  await page.getByRole("button", { name: "Fail next request", exact: true }).click();
  await page.getByRole("button", { name: "Take request", exact: true }).click();
  await expect(page.getByRole("region", { name: "Support queue", exact: true }).getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Take request", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Refresh queue", exact: true }).click();
  await page.getByRole("button", { name: "Take request", exact: true }).click();
  await expect(page.getByText("Sample request updated: In progress. No real handoff occurred.")).toBeVisible();
});

test("refill cancel creates no record; explicit confirm records only submitted and prevents duplicates", async ({ page }) => {
  await page.goto(demo);
  await page.getByRole("button", { name: "Prescription refills", exact: true }).click();
  await page.getByLabel("Medication to refill", { exact: true }).selectOption("demo-medication");
  await page.getByRole("button", { name: "Review refill request", exact: true }).click();
  await expect(page.getByText("REVIEW REFILL", { exact: true })).toBeVisible();
  await expect(page.getByText("No refill requests yet.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByText("No refill requests yet.")).toBeVisible();
  await page.getByRole("button", { name: "Review refill request", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  const history = page.getByRole("region", { name: "Refill request history", exact: true });
  await expect(history.getByText("Submitted for review", { exact: true })).toBeVisible();
  await expect(history.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeDisabled();
  await expect(page.getByText("Sample refill submitted for review. No pharmacy was contacted or refill approved.")).toBeVisible();
});

test("exhausted refills lead to an editable doctor message without auto-sending", async ({ page }) => {
  await page.goto(demo);
  await page.getByRole("button", { name: "Prescription refills", exact: true }).click();
  await page.getByLabel("Medication to refill", { exact: true }).selectOption("demo-medication-no-refills");
  await expect(page.getByText("No refills remain. Contact your doctor for the next step.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Contact my doctor", exact: true }).click();
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue(/refilling Metformin, 500 mg/);
  await expect(page.getByRole("button", { name: "Review message", exact: true })).toBeDisabled();
  await expect(page.getByText("No messages yet.")).toBeVisible();
});

test("live unavailable services and unknown refill counts never fabricate requests or samples", async ({ page }) => {
  await liveSession(page);
  const writes = [];
  page.on("request", (request) => { if (request.method() === "POST" && !request.url().includes("auth/")) writes.push(request.url()); });
  await page.goto(live);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await expect(page.getByRole("button", { name: "Review help request", exact: true })).toBeEnabled();
  await expect(page.getByRole("region", { name: "Your help requests" })).toHaveCount(0);
  await page.getByRole("button", { name: "Prescription refills", exact: true }).click();
  await page.getByLabel("Medication to refill", { exact: true }).selectOption("med-1");
  await expect(page.getByText("Remaining refills are unknown. Check with your doctor.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeDisabled();
  await expect(page.getByRole("region", { name: "Refill request history", exact: true }).getByRole("alert")).toBeVisible();
  await expect(page.getByRole("region", { name: "Refill request history", exact: true }).getByRole("listitem")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Preview support queue", exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("support-agent login uses a separate workspace without older-adult data requests", async ({ page }) => {
  await liveSession(page, "support_agent");
  const paths = [];
  page.on("request", (request) => { if (request.url().includes("/api/v1/")) paths.push(new URL(request.url()).pathname); });
  await page.goto(live);
  await expect(page.getByRole("heading", { name: "Support queue", exact: true })).toBeVisible();
  await expect(page.getByText("No requests in this view.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "My care", exact: true })).toHaveCount(0);
  expect(paths.some((path) => /notifications|actions|older-adults/.test(path))).toBe(false);
});

test("caregivers have no accidental self-refill or support queue access", async ({ page }) => {
  await liveSession(page, "caregiver"); await page.goto(live);
  await expect(page.getByRole("heading", { name: "Caregiver setup", exact: true })).toBeVisible();
  for (const name of ["Help", "Prescription refills", "Preview support queue"])
    await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);
});

test("Help validation and all three screens fit 320px with larger text", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 320, height: 850 });
  await page.goto(demo);
  await page.getByRole("button", { name: "Larger text", exact: true }).click();
  await openHelp(page);
  await page.getByLabel("What do you need help with?", { exact: true }).fill("   ");
  await expect(page.getByRole("button", { name: "Review help request", exact: true })).toBeEnabled();
  await page.getByLabel("What do you need help with?", { exact: true }).fill("x".repeat(300));
  await expect(page.getByRole("button", { name: "Review help request", exact: true })).toBeEnabled();
  await expect(page.getByText("No help requests yet.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "My care", exact: true }).screenshot({ path: testInfo.outputPath("help-mobile.png") });
  await page.getByRole("button", { name: "Prescription refills", exact: true }).click();
  await page.getByLabel("Medication to refill", { exact: true }).selectOption("demo-medication-no-refills");
  await expect(page.getByText("No refill requests yet.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "My care", exact: true }).screenshot({ path: testInfo.outputPath("refills-mobile.png") });
  await page.getByRole("button", { name: "Preview support queue", exact: true }).click();
  await page.getByRole("button", { name: "View request from Alex (sample)", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "My care", exact: true }).screenshot({ path: testInfo.outputPath("queue-mobile.png") });
});
