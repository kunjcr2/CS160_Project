import { test, expect } from "./fixtures.js";
const live = "http://127.0.0.1:5181";
const doctor = { id: "doctor1", name: "Dr. Chen", specialty: "Cardiology", location: "Clinic" };
const start = () => new Date(Date.now() + 3 * 86400000).toISOString();
const action = (type) => ({ id: "change1", action_type: type, summary_text: type === "cancel_appointment" ? "Cancel the original appointment?" : "Move the original appointment to the new time?", status: "proposed", expires_at: new Date(Date.now() + 300000).toISOString() });

async function setup(page) {
  const visit = { id: "visit1", provider: doctor, starts_at: start(), ends_at: start(), location: "Clinic", status: "booked" };
  const slot = { slot_id: "opaque:new/slot", provider: doctor, starts_at: new Date(Date.now() + 4 * 86400000).toISOString(), ends_at: new Date(Date.now() + 4 * 86400000 + 1800000).toISOString(), label: "New time" };
  const state = { visits: [visit], slot, pending: null, proposals: [], confirms: 0, searches: [], notifications: 0 };
  await page.route("**/api/v1/auth/refresh", (r) => r.fulfill({ json: { access_token: "token" } }));
  await page.route("**/api/v1/users/me", (r) => r.fulfill({ json: { id: "older1", role: "older_adult", display_name: "Maggie", timezone: "America/New_York" } }));
  await page.route("**/api/v1/notifications", (r) => { state.notifications++; return r.fulfill({ json: [] }); });
  await page.route("**/api/v1/providers", (r) => r.fulfill({ json: [doctor] }));
  await page.route("**/api/v1/appointments", (r) => r.fulfill({ json: state.visits }));
  await page.route("**/api/v1/slots?*", (r) => { state.searches.push(new URL(r.request().url()).searchParams.get("provider_id")); return r.fulfill({ json: [state.slot] }); });
  await page.route("**/api/v1/actions/pending", (r) => r.fulfill({ json: { action: state.pending } }));
  await page.route("**/api/v1/actions", (r) => {
    const body = r.request().postDataJSON(); state.proposals.push(body); state.pending = action(body.action_type);
    return r.fulfill({ status: 201, json: state.pending });
  });
  await page.route("**/api/v1/actions/change1/cancel", (r) => {
    const old = state.pending; state.pending = null;
    return r.fulfill({ json: { action: { ...old, status: "cancelled" }, message: "The original appointment was kept." } });
  });
  await page.route("**/api/v1/actions/change1/confirm", (r) => {
    const old = state.pending; state.pending = null; state.confirms++;
    state.visits = old.action_type === "cancel_appointment" ? [] : [{ ...visit, id: "new-visit", starts_at: state.slot.starts_at }];
    return r.fulfill({ json: { action: { ...old, status: "executed", result: { appointment_id: "new-visit", previous_appointment_id: "visit1" } }, message: "Appointment updated." } });
  });
  return state;
}

test("cancel proposal leaves booking intact until confirm and refreshes reminders afterward", async ({ page }) => {
  const state = await setup(page); await page.goto(live);
  await page.getByRole("button", { name: "Find appointments", exact: true }).click();
  await page.getByRole("button", { name: "Cancel appointment", exact: true }).click();
  await expect(page.getByText("REVIEW CANCELLATION", { exact: true })).toBeVisible();
  expect(state.visits.length).toBe(1); expect(state.confirms).toBe(0);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByText("The original appointment was kept.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel appointment", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).evaluate((b) => { b.click(); b.click(); });
  await expect(page.getByText("No upcoming appointments.")).toBeVisible();
  expect(state.confirms).toBe(1);
  expect(state.proposals[0]).toEqual({ action_type: "cancel_appointment", payload: { appointment_id: "visit1" } });
  expect(state.notifications).toBeGreaterThan(1);
});

test("rescheduling locks the same doctor, uses opaque slot ID and refreshes only after confirmation", async ({ page }) => {
  const state = await setup(page); await page.goto(live);
  await page.getByRole("button", { name: "Find appointments", exact: true }).click();
  await page.getByRole("button", { name: "Reschedule appointment", exact: true }).click();
  await expect(page.getByRole("combobox")).toBeDisabled();
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await page.getByRole("button", { name: "Review this time", exact: true }).click();
  await expect(page.getByText("REVIEW RESCHEDULE", { exact: true })).toBeVisible();
  expect(state.searches).toEqual(["doctor1"]);
  expect(state.proposals[0]).toEqual({ action_type: "reschedule_appointment", payload: { appointment_id: "visit1", slot_id: "opaque:new/slot" } });
  expect(state.visits[0].id).toBe("visit1"); expect(state.confirms).toBe(0);
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Appointment updated.")).toBeVisible();
  await expect(page.getByText("Clinic · booked", { exact: true })).toBeVisible();
  expect(state.visits[0].id).toBe("new-visit"); expect(state.confirms).toBe(1);
});

test("reschedule conflict and provider failure do not remove the original appointment", async ({ page }) => {
  const state = await setup(page);
  await page.route("**/api/v1/actions/change1/confirm", (r) => {
    const old = state.pending; state.pending = null;
    return r.fulfill({ json: { action: { ...old, status: "failed", result: null }, message: "The selected time was taken. Choose another time." } });
  });
  await page.goto(live); await page.getByRole("button", { name: "Find appointments", exact: true }).click();
  await page.getByRole("button", { name: "Reschedule appointment", exact: true }).click();
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await page.getByRole("button", { name: "Review this time", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("The selected time was taken. Choose another time.")).toBeVisible();
  await expect(page.getByText("Clinic · booked", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reschedule appointment", exact: true })).toBeEnabled();
  expect(state.visits[0].id).toBe("visit1");
});

test("already started and cancelled appointments have no change controls", async ({ page }) => {
  const state = await setup(page);
  state.visits = [
    { ...state.visits[0], starts_at: "2020-01-01T12:00:00Z" },
    { ...state.visits[0], id: "cancelled", status: "cancelled" },
  ];
  await page.goto(live); await page.getByRole("button", { name: "Find appointments", exact: true }).click();
  await expect(page.getByText("Clinic · cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel appointment", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reschedule appointment", exact: true })).toHaveCount(0);
});
