import { test, expect } from "./fixtures.js";
const live = "http://127.0.0.1:5181";
const doctor = { id: "doctor1", name: "Dr. Chen", specialty: "Cardiology", location: "Clinic" };
const med = { id: "med1", name: "Lisinopril", dosage: "10 mg", refills_remaining: 2, schedules: [], stopped_at: null };
const assistance = { id: "help1", older_adult_id: "older1", older_adult_name: "Maggie", summary: "Help with appointments", reason: "user_request", status: "open", assigned_to_name: null, created_at: "2026-11-19T17:00:00Z", resolved_at: null };
const action = (type) => ({ id: "action1", action_type: type, summary_text: `Please confirm ${type}.`, status: "proposed", expires_at: new Date(Date.now() + 300000).toISOString(), result: null });
const refill = () => ({ id: "refill1", medication: { ...med, refills_remaining: 1 }, status: "requested", status_message: "Your Lisinopril refill was requested.", created_at: new Date().toISOString() });

async function setup(page, role = "older_adult") {
  const state = { pending: null, proposals: [], confirms: 0, medications: [{ ...med }], refills: [], queue: [{ ...assistance }], patches: [] };
  await page.route("**/api/v1/auth/refresh", (r) => r.fulfill({ json: { access_token: "live-token" } }));
  await page.route("**/api/v1/users/me", (r) => r.fulfill({ json: { id: "older1", role, display_name: "Test user", timezone: "America/New_York" } }));
  await page.route("**/api/v1/notifications", (r) => r.fulfill({ json: [] }));
  await page.route("**/api/v1/providers", (r) => r.fulfill({ json: [doctor] }));
  await page.route("**/api/v1/actions/pending", (r) => r.fulfill({ json: { action: state.pending } }));
  await page.route("**/api/v1/older-adults/older1/medications", (r) => r.fulfill({ json: state.medications }));
  await page.route("**/api/v1/older-adults/older1/refills", (r) => r.fulfill({ json: state.refills }));
  await page.route("**/api/v1/assistance/queue", (r) => r.fulfill({ json: state.queue }));
  await page.route("**/api/v1/actions", (r) => {
    const body = r.request().postDataJSON(); state.proposals.push(body); state.pending = action(body.action_type);
    expect(r.request().headers().authorization).toBe("Bearer live-token");
    return r.fulfill({ status: 201, json: state.pending });
  });
  await page.route("**/api/v1/actions/action1/confirm", (r) => {
    state.confirms++;
    const type = state.pending.action_type;
    const result = type === "request_refill" ? { refill_request_id: "refill1" } : { assistance_request_id: "help1" };
    if (type === "request_refill") { state.refills = [refill()]; state.medications[0].refills_remaining = 1; }
    state.pending = null;
    return r.fulfill({ json: { action: { ...action(type), status: "executed", result }, message: "Your request was saved." } });
  });
  await page.route("**/api/v1/actions/action1/cancel", (r) => {
    const old = state.pending; state.pending = null;
    return r.fulfill({ json: { action: { ...old, status: "cancelled" }, message: "No request was sent." } });
  });
  await page.route("**/api/v1/assistance/help1", (r) => {
    const body = r.request().postDataJSON(); state.patches.push(body);
    const row = { ...assistance, status: body.status, assigned_to_name: "Agent One" };
    state.queue = body.status === "resolved" ? [] : [row];
    return r.fulfill({ json: row });
  });
  return state;
}

async function openRefill(page) {
  await page.getByRole("button", { name: "Prescription refills", exact: true }).click();
  await page.getByLabel("Medication to refill", { exact: true }).selectOption("med1");
}

test("live Help uses reviewed 300-character summary, confirm only, and receipt without agent reads", async ({ page }) => {
  const state = await setup(page); const paths = [];
  page.on("request", (r) => paths.push(new URL(r.url()).pathname));
  await page.goto(live);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await page.getByLabel("What do you need help with?", { exact: true }).fill("Please help with appointments.");
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveAttribute("maxlength", "300");
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  expect(state.proposals).toEqual([{ action_type: "request_help", payload: { older_adult_id: "older1", summary: "Please help with appointments.", reason: "user_request" } }]);
  expect(state.confirms).toBe(0);
  await page.getByRole("button", { name: "Confirm", exact: true }).evaluate((b) => { b.click(); b.click(); });
  await expect(page.getByRole("region", { name: "Help submission" }).getByRole("heading", { name: "Help request submitted" })).toBeVisible();
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveValue("");
  expect(state.confirms).toBe(1);
  expect(paths.some((path) => path.includes("/assistance"))).toBe(false);
});

test("pending Help recovers after reload; cancelling keeps a local draft and never submits", async ({ page }) => {
  const state = await setup(page); await page.goto(live);
  await page.getByRole("button", { name: "Help", exact: true }).click();
  await page.getByLabel("What do you need help with?", { exact: true }).fill("My question");
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByLabel("What do you need help with?", { exact: true })).toHaveValue("My question");
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  await page.reload();
  await expect(page.getByText("REVIEW HELP REQUEST", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm", exact: true })).toHaveCount(0);
  expect(state.confirms).toBe(0);
});

test("refill confirmation refreshes counts, blocks duplicate open request, and polling shows ready", async ({ page }) => {
  const state = await setup(page); await page.clock.install(); await page.goto(live); await openRefill(page);
  await page.getByRole("button", { name: "Review refill request", exact: true }).click();
  expect(state.confirms).toBe(0);
  expect(state.proposals[0]).toEqual({ action_type: "request_refill", payload: { older_adult_id: "older1", medication_id: "med1" } });
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Refills remaining: 1", { exact: true })).toBeVisible();
  const history = page.getByRole("region", { name: "Refill request history" });
  await expect(history.getByText("Your Lisinopril refill was requested.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeDisabled();
  state.refills[0] = { ...state.refills[0], status: "ready", status_message: "Your Lisinopril refill is ready." };
  await page.clock.runFor(20100);
  await expect(history.getByText("Your Lisinopril refill is ready.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeEnabled();
});

test("pharmacy failure in a 200 response keeps counts and never claims saved or ready", async ({ page }) => {
  const state = await setup(page);
  await page.route("**/api/v1/actions/action1/confirm", (r) => {
    state.pending = null;
    return r.fulfill({ json: { action: { ...action("request_refill"), status: "failed" }, message: "The pharmacy is unavailable. Try again later." } });
  });
  await page.goto(live); await openRefill(page);
  await page.getByRole("button", { name: "Review refill request", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("form", { name: "Request a prescription refill" }).getByRole("alert")).toHaveText("The pharmacy is unavailable. Try again later.");
  await expect(page.getByText("Refills remaining: 2", { exact: true })).toBeVisible();
  await expect(page.getByText("No refill requests yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeEnabled();
});

test("unknown confirmation outcome retries same action rather than resubmitting refill", async ({ page }) => {
  const state = await setup(page); let calls = 0;
  await page.route("**/api/v1/actions/action1/confirm", (r) => {
    calls++;
    if (calls === 1) return r.abort("failed");
    state.pending = null; state.refills = [refill()]; state.medications[0].refills_remaining = 1;
    return r.fulfill({ json: { action: { ...action("request_refill"), status: "executed", result: { refill_request_id: "refill1" } }, message: "Saved once." } });
  });
  await page.goto(live); await openRefill(page);
  await page.getByRole("button", { name: "Review refill request", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("button", { name: "Review refill request", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Saved once.")).toBeVisible();
  expect(state.proposals.length).toBe(1); expect(calls).toBe(2);
});

for (const role of ["support_agent", "admin"]) test(`${role} can take and resolve live requests without pretending to have resolved history`, async ({ page }) => {
  const state = await setup(page, role); await page.goto(live);
  await page.getByRole("button", { name: "View request from Maggie", exact: true }).click();
  await expect(page.getByRole("region", { name: "Request details" }).getByText("Help with appointments")).toBeVisible();
  await page.getByRole("button", { name: "Take request", exact: true }).click();
  await expect(page.getByText("Request updated: In progress.", { exact: true })).toBeVisible();
  await page.getByLabel("Queue status", { exact: true }).selectOption("in_progress");
  await page.getByRole("button", { name: "View request from Maggie", exact: true }).click();
  await page.getByRole("button", { name: "Mark resolved", exact: true }).click();
  await expect(page.getByText("No requests in this view.")).toBeVisible();
  expect(state.patches).toEqual([{ status: "in_progress" }, { status: "resolved" }]);
  await expect(page.getByLabel("Queue status", { exact: true }).locator('option[value="resolved"]')).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "My care", exact: true })).toHaveCount(0);
});

test("another agent's claim returns 409; refresh shows server assignment without false success", async ({ page }) => {
  const state = await setup(page, "support_agent");
  await page.route("**/api/v1/assistance/help1", (r) => {
    state.queue[0] = { ...assistance, status: "in_progress", assigned_to_name: "Another agent" };
    return r.fulfill({ status: 409, json: { detail: { code: "in_progress", message: "This request can't be changed that way." } } });
  });
  await page.goto(live);
  await page.getByRole("button", { name: "View request from Maggie", exact: true }).click();
  await page.getByRole("button", { name: "Take request", exact: true }).click();
  await expect(page.getByRole("region", { name: "Support queue" }).getByRole("alert")).toBeVisible();
  await expect(page.getByText("Request updated: In progress.", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Refresh queue", exact: true }).click();
  await page.getByLabel("Queue status", { exact: true }).selectOption("in_progress");
  await page.getByRole("button", { name: "View request from Maggie", exact: true }).click();
  await expect(page.getByText("Assigned to Another agent", { exact: true })).toBeVisible();
});

test("AI failure count offers Help and creates no action until the user reviews it", async ({ page }) => {
  const state = await setup(page); const turns = [];
  await page.route("**/api/v1/ai/process", (r) => {
    turns.push(r.request().postDataJSON().unclear_turns);
    return r.fulfill({ json: { reply: "Could you try another way?", proposal: null, unclear_turns: turns.length, offer_human_help: turns.length === 3 } });
  });
  await page.goto(live);
  for (let i = 0; i < 3; i++) {
    await page.getByLabel("Your message", { exact: true }).fill(`Unclear question ${i}`);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByRole("log").getByText("Could you try another way?", { exact: true })).toHaveCount(i + 1);
  }
  expect(turns).toEqual([0, 1, 2]); expect(state.proposals).toEqual([]);
  await page.getByRole("button", { name: "Review support options", exact: true }).click();
  await page.getByRole("button", { name: "Review help request", exact: true }).click();
  expect(state.proposals[0].payload).toEqual({ older_adult_id: "older1", summary: "", reason: "repeated_failures" });
  expect(state.confirms).toBe(0);
});

test("live support and refill screens fit 320px with long names and larger text", async ({ page }, testInfo) => {
  const state = await setup(page, "admin"); state.queue[0].older_adult_name = "Maggie".repeat(18);
  await page.setViewportSize({ width: 320, height: 850 }); await page.goto(live);
  await page.getByRole("button", { name: "Larger text", exact: true }).click();
  await page.getByRole("button", { name: `View request from ${state.queue[0].older_adult_name}`, exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("live-support-mobile.png"), fullPage: true });
  const patient = await setup(page);
  patient.refills = [{ ...refill(), status: "ready", status_message: "Your Lisinopril refill is ready." }];
  await page.goto(live);
  await page.getByRole("button", { name: "Larger text", exact: true }).click();
  await openRefill(page);
  await expect(page.getByText("Your Lisinopril refill is ready.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("region", { name: "My care", exact: true }).screenshot({ path: testInfo.outputPath("live-refill-mobile.png") });
});
