import { test, expect } from "./fixtures.js";

const live = "http://127.0.0.1:5181";
const doctor = {
  id: "doctor-1",
  name: "Dr. Chen",
  specialty: "Cardiology",
  location: "Clinic",
};
const slot = {
  slot_id: "opaque:slot/1",
  provider: doctor,
  starts_at: "2026-11-20T18:30:00Z",
  ends_at: "2026-11-20T19:00:00Z",
  label: "Friday at 10:30 AM",
};
const action = () => ({
  id: "action-1",
  action_type: "book_appointment",
  summary_text: "Book Dr. Chen on Friday at 10:30 AM?",
  status: "proposed",
  expires_at: new Date(Date.now() + 300000).toISOString(),
  result: null,
});
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "test-token" } }),
  );
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({
      json: {
        id: "older-1",
        role: "older_adult",
        display_name: "Margaret",
        timezone: "America/New_York",
      },
    }),
  );
  await page.route("**/api/v1/notifications", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/providers", (route) =>
    route.fulfill({ json: [doctor] }),
  );
  await page.route("**/api/v1/appointments", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/slots?*", (route) =>
    route.fulfill({ json: [slot] }),
  );
});

test("slot selection proposes only; explicit confirmation books and refreshes appointments", async ({
  page,
}) => {
  let confirms = 0;
  await page.route("**/api/v1/actions", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      action_type: "book_appointment",
      payload: { slot_id: slot.slot_id },
    });
    expect(route.request().headers().authorization).toBe("Bearer test-token");
    await route.fulfill({ status: 201, json: action() });
  });
  await page.route("**/api/v1/actions/action-1/confirm", async (route) => {
    confirms++;
    await route.fulfill({
      json: {
        action: { ...action(), status: "executed" },
        message: "Your appointment is booked.",
      },
    });
  });
  await page.route("**/api/v1/appointments", (route) =>
    route.fulfill({
      json: confirms
        ? [{ ...slot, id: "visit-1", location: "Clinic", status: "booked" }]
        : [],
    }),
  );
  await page.goto(live);
  await page
    .getByRole("button", { name: "Book an appointment", exact: true })
    .click();
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await expect(page.getByText("Nov 20, 1:30 PM EST")).toBeVisible();
  await page.getByRole("button", { name: "Review this time" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toBeVisible();
  expect(confirms).toBe(0);
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Your appointment is booked.")).toBeVisible();
  await expect(page.getByText("Clinic · booked")).toBeVisible();
  expect(confirms).toBe(1);
});

test("reload restores pending action; a failed booking is not shown as success", async ({
  page,
}) => {
  let pending = action();
  await page.route("**/api/v1/actions/pending", (route) =>
    route.fulfill({ json: { action: pending } }),
  );
  await page.route("**/api/v1/actions/action-1/confirm", (route) => {
    pending = null;
    return route.fulfill({
      json: {
        action: { ...action(), status: "failed" },
        message:
          "That time is no longer available. Please choose another time.",
      },
    });
  });
  await page.goto(live);
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Your message", { exact: true })).toBeDisabled();
  await page.reload();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("no longer available");
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
});

test("lost proposal response recovers the saved action before allowing another request", async ({
  page,
}) => {
  let pending = null;
  await page.route("**/api/v1/actions/pending", (route) =>
    route.fulfill({ json: { action: pending } }),
  );
  await page.route("**/api/v1/actions", (route) => {
    pending = action();
    return route.abort("failed");
  });
  await page.goto(live);
  await page
    .getByRole("button", { name: "Find appointments", exact: true })
    .click();
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await page.getByRole("button", { name: "Review this time" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review this time" }),
  ).toBeDisabled();
});

test("pending lookup failure blocks replacement and can be retried", async ({
  page,
}) => {
  let broken = true;
  await page.route("**/api/v1/actions/pending", (route) =>
    route.fulfill(
      broken
        ? { status: 503, json: { detail: "Temporarily unavailable" } }
        : { json: { action: null } },
    ),
  );
  await page.goto(live);
  await expect(
    page.getByRole("button", { name: "Retry pending confirmation" }),
  ).toBeVisible();
  await expect(page.getByLabel("Your message", { exact: true })).toBeDisabled();
  broken = false;
  await page
    .getByRole("button", { name: "Retry pending confirmation" })
    .click();
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
});

test("daily doses use profile date, only sent is actionable, and automatic missed is refreshed", async ({
  page,
}) => {
  // UTC date is Nov 15, but New York is still Nov 14.
  await page.clock.install({ time: new Date("2026-11-15T02:00:00Z") });
  let current = "sent";
  const dose = {
    id: "dose-1",
    medication_id: "med-1",
    medication_name: "Metformin",
    dosage: "500 mg",
    due_at: "2026-11-15T01:00:00Z",
    attempts: 2,
    confirmed_at: null,
  };
  await page.route("**/api/v1/older-adults/older-1/medications", (route) =>
    route.fulfill({
      json: [
        {
          id: "med-1",
          name: "Metformin",
          dosage: "500 mg",
          instructions: "Take with food",
          schedules: [
            { time_of_day: "20:00:00", days_of_week: [0, 1, 2, 3, 4, 5, 6] },
          ],
        },
      ],
    }),
  );
  await page.route(
    "**/api/v1/older-adults/older-1/medication-reminders?*",
    (route) => {
      expect(new URL(route.request().url()).searchParams.get("date")).toBe(
        "2026-11-14",
      );
      return route.fulfill({
        json: [
          { ...dose, status: current },
          { ...dose, id: "later", status: "scheduled", attempts: 0 },
        ],
      });
    },
  );
  await page.route("**/api/v1/medication-reminders/dose-1/taken", (route) => {
    expect(route.request().postData()).toBeNull();
    current = "taken";
    return route.fulfill({ json: { ...dose, status: current } });
  });
  await page.goto(live);
  await page
    .getByRole("button", { name: "My medications", exact: true })
    .click();
  const daily = page.getByLabel("Daily doses", { exact: true });
  await expect(page.getByLabel("Dose date")).toHaveValue("2026-11-14");
  await expect(
    daily.getByRole("button", { name: "Taken", exact: true }),
  ).toHaveCount(1);
  await expect(daily.getByText("Second reminder")).toBeVisible();
  await daily.getByRole("button", { name: "Taken", exact: true }).click();
  await expect(daily.getByRole("button")).toHaveCount(0);
  current = "missed";
  await page.clock.fastForward(21000);
  await expect(daily.getByText("Missed", { exact: true })).toBeVisible();
  await expect(daily.getByRole("button")).toHaveCount(0);
});

test("empty slots, provider outage and narrow layout remain usable", async ({
  page,
}, testInfo) => {
  let unavailable = false;
  await page.route("**/api/v1/slots?*", (route) =>
    route.fulfill(
      unavailable
        ? {
            status: 503,
            json: {
              detail: {
                code: "provider_unavailable",
                message: "Please try later.",
              },
            },
          }
        : { json: [] },
    ),
  );
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto(live);
  await page
    .getByRole("button", { name: "Find appointments", exact: true })
    .click();
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await expect(page.getByText(/No available times/)).toBeVisible();
  unavailable = true;
  await page.getByRole("button", { name: "Find times", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Please try later.");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("appointment-search-mobile.png"),
    fullPage: true,
  });
});
