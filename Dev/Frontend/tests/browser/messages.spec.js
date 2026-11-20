import { test, expect } from "./fixtures.js";
const live = "http://127.0.0.1:5181";
const doctor = { id: "provider-1", name: "Dr. Chen", specialty: "Cardiology", location: "Clinic", phone: null };
const text = "Could you explain my appointment instructions?";
const proposal = () => ({ id: "message-action", action_type: "send_care_message", summary_text: `I will send Dr. Chen: "${text}". Should I send it?`, status: "proposed", expires_at: new Date(Date.now() + 300000).toISOString(), result: null });
const historyRow = (status = "sent") => ({ id: "message-1", provider: doctor, body: text, status, created_at: "2026-11-16T18:30:00Z" });

async function setup(page) {
  const state = { pending: null, messages: [], proposals: [], confirms: 0, cancels: 0 };
  await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ json: { access_token: "message-token" } }));
  await page.route("**/api/v1/users/me", (route) => route.fulfill({ json: { id: "older-1", role: "older_adult", display_name: "Margaret", timezone: "America/New_York" } }));
  await page.route("**/api/v1/notifications", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/providers", (route) => route.fulfill({ json: [doctor] }));
  await page.route("**/api/v1/actions/pending", (route) => route.fulfill({ json: { action: state.pending } }));
  await page.route("**/api/v1/older-adults/older-1/messages", (route) => route.fulfill({ json: state.messages }));
  await page.route("**/api/v1/actions", (route) => {
    state.proposals.push(route.request().postDataJSON()); state.pending = proposal();
    expect(route.request().headers().authorization).toBe("Bearer message-token");
    return route.fulfill({ status: 201, json: state.pending });
  });
  await page.route("**/api/v1/actions/message-action/confirm", async (route) => {
    state.confirms++; state.pending = null; state.messages = [historyRow()];
    return route.fulfill({ json: { action: { ...proposal(), status: "executed", result: { ok: true, message_id: "message-1" } }, message: "Done. Your message was sent to Dr. Chen." } });
  });
  await page.route("**/api/v1/actions/message-action/cancel", (route) => {
    state.cancels++; state.pending = null;
    return route.fulfill({ json: { action: { ...proposal(), status: "cancelled" }, message: "Okay, I won't do that." } });
  });
  return state;
}

async function compose(page) {
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await page.getByLabel("Doctor to message", { exact: true }).selectOption(doctor.id);
  await page.getByLabel("Message to your doctor", { exact: true }).fill(text);
}

test("review does not send; explicit confirm sends once and refreshes history", async ({ page }) => {
  const state = await setup(page); await page.goto(live); await compose(page);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  expect(state.proposals).toEqual([{ action_type: "send_care_message", payload: { older_adult_id: "older-1", provider_id: doctor.id, body: text } }]);
  expect(state.confirms).toBe(0);
  await expect(page.getByText("REVIEW MESSAGE", { exact: true })).toBeVisible();
  await expect(page.getByText("REVIEW APPOINTMENT", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Confirm", exact: true }).evaluate((button) => { button.click(); button.click(); });
  const history = page.getByRole("region", { name: "Message history", exact: true });
  await expect(history.getByText(text, { exact: true })).toBeVisible();
  await expect(history.getByText("Sent", { exact: true })).toBeVisible();
  await expect(history.getByText("Nov 16, 1:30 PM EST")).toBeVisible();
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue("");
  expect(state.confirms).toBe(1);
});

test("cancel never sends and preserves the draft across panel changes", async ({ page }) => {
  const state = await setup(page); await page.goto(live); await compose(page);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue(text);
  expect(state.confirms).toBe(0); expect(state.cancels).toBe(1);
  await expect(page.getByText("No messages yet.")).toBeVisible();
});

test("executed command with ok false reports failure and retains text for a new reviewed attempt", async ({ page }) => {
  const state = await setup(page);
  await page.route("**/api/v1/actions/message-action/confirm", (route) => {
    state.confirms++; state.pending = null; state.messages = [historyRow("failed")];
    return route.fulfill({ json: { action: { ...proposal(), status: "executed", result: { ok: false, message_id: "message-1" } }, message: "I couldn't send your message to Dr. Chen right now. Please try again later." } });
  });
  await page.goto(live); await compose(page);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("region", { name: "Message history", exact: true }).getByText("Failed to send", { exact: true })).toBeVisible();
  await expect(page.getByText("Sent", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue(text);
  await expect(page.getByRole("button", { name: "Review message", exact: true })).toBeEnabled();
  expect(state.proposals.length).toBe(1); expect(state.confirms).toBe(1);
});

test("lost confirmation response retries the same action rather than creating another message", async ({ page }) => {
  const state = await setup(page);
  await page.route("**/api/v1/actions/message-action/confirm", (route) => {
    state.confirms++;
    if (state.confirms === 1) return route.abort("failed");
    state.pending = null; state.messages = [historyRow()];
    return route.fulfill({ json: { action: { ...proposal(), status: "executed", result: { ok: true, message_id: "message-1" } }, message: "Done. Your message was sent to Dr. Chen." } });
  });
  await page.goto(live); await compose(page);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("button", { name: "Review message", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("region", { name: "Message history", exact: true }).getByText("Sent", { exact: true })).toBeVisible();
  expect(state.proposals.length).toBe(1); expect(state.confirms).toBe(2);
});

test("pending message survives reload with correct card; cancellation clears it", async ({ page }) => {
  const state = await setup(page); state.pending = proposal();
  await page.goto(live); await expect(page.getByText("REVIEW MESSAGE", { exact: true })).toBeVisible();
  await page.reload(); await expect(page.getByRole("heading", { name: proposal().summary_text })).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirm", exact: true })).toHaveCount(0);
  expect(state.confirms).toBe(0); expect(state.cancels).toBe(1);
});

test("backend refusals keep the draft and do not create a confirmation", async ({ page }) => {
  const state = await setup(page);
  await page.route("**/api/v1/actions", (route) => route.fulfill({ status: 409, json: { detail: { code: "not_allowed", message: "I can't send a message for that person." } } }));
  await page.goto(live); await compose(page);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  await expect(page.getByRole("form", { name: "Write to your doctor" }).getByRole("alert")).toHaveText("I can't send a message for that person.");
  await expect(page.getByRole("button", { name: "Confirm", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue(text);
  expect(state.confirms).toBe(0);
});

test("missing API never falls back to sample history; retry works without losing the draft", async ({ page }) => {
  const state = await setup(page); let missing = true;
  await page.route("**/api/v1/older-adults/older-1/messages", (route) => route.fulfill(missing ? { status: 404, json: { detail: "Not found" } } : { json: [historyRow()] }));
  await page.goto(live); await compose(page);
  const history = page.getByRole("region", { name: "Message history", exact: true });
  await expect(history.getByRole("alert")).toBeVisible();
  await expect(history.getByRole("article")).toHaveCount(0);
  missing = false; await page.getByRole("button", { name: "Refresh messages", exact: true }).click();
  await expect(history.getByText(text, { exact: true })).toBeVisible();
  await expect(page.getByLabel("Message to your doctor", { exact: true })).toHaveValue(text);
  expect(state.proposals.length).toBe(0);
});

test("required doctor/body, empty doctor list, length limit and 320px layout", async ({ page }, testInfo) => {
  await setup(page); await page.setViewportSize({ width: 320, height: 850 });
  await page.goto(live);
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  const review = page.getByRole("button", { name: "Review message", exact: true });
  await expect(review).toBeDisabled();
  await page.getByLabel("Doctor to message", { exact: true }).selectOption(doctor.id);
  await page.getByLabel("Message to your doctor", { exact: true }).fill("   ");
  await expect(review).toBeDisabled();
  await page.getByLabel("Message to your doctor", { exact: true }).fill("x".repeat(2000));
  await expect(page.getByText("2000 / 2000 characters")).toBeVisible();
  await expect(review).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("message-doctor-mobile.png"), fullPage: true });
  await page.route("**/api/v1/providers", (route) => route.fulfill({ json: [] }));
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await expect(page.getByText("No doctors are available to message.")).toBeVisible();
  await expect(review).toBeDisabled();
});

test("caregiver is not accidentally used as the older-adult id", async ({ page }) => {
  await setup(page);
  await page.route("**/api/v1/users/me", (route) => route.fulfill({ json: { id: "caregiver-1", role: "caregiver", display_name: "Daniel", timezone: "America/Los_Angeles" } }));
  await page.goto(live);
  await expect(page.getByRole("heading", { name: "Caregiver setup", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Message my doctor", exact: true })).toHaveCount(0);
});

test("demo messaging is visibly simulated and records only after confirmation", async ({ page }) => {
  await page.goto("http://127.0.0.1:5180");
  await page.getByRole("button", { name: "Message my doctor", exact: true }).click();
  await page.getByLabel("Doctor to message", { exact: true }).selectOption("demo-doctor");
  await page.getByLabel("Message to your doctor", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Review message", exact: true }).click();
  await expect(page.getByText("No messages yet.")).toBeVisible();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Sample message sent. Nothing was delivered to a real doctor.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Message history", exact: true }).getByText(text)).toBeVisible();
});
