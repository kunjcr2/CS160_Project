import { test, expect } from "@playwright/test";

const demo = "http://127.0.0.1:5180";
const live = "http://127.0.0.1:5181";
const medication = (page) =>
  page.getByRole("article", { name: "Medication reminder", exact: true });
const fixture = {
  id: "dose-1",
  medication_name: "Lisinopril",
  dosage: "10 mg",
  due_at: "2026-10-13T15:00:00Z",
  status: "sent",
  message: "Time to take your Lisinopril, 10 mg.",
};

test("demo reminder actions, automatic missed and appointment acknowledgement", async ({
  page,
}) => {
  await page.goto(demo);
  await expect(page.getByText("Demo mode", { exact: true })).toBeVisible();
  await medication(page)
    .getByRole("button", { name: "Taken", exact: true })
    .click();
  await expect(
    medication(page).getByText("Taken", { exact: true }),
  ).toBeVisible();
  await expect(medication(page).getByRole("button")).toHaveCount(0);
  await page.getByRole("button", { name: "OK", exact: true }).click();
  await expect(page.getByText("Acknowledged", { exact: true })).toBeVisible();
  await page.getByText("Demo controls", { exact: true }).click();
  await page.getByRole("button", { name: "Reset reminders" }).click();
  await expect(
    medication(page).getByRole("button", { name: "Taken", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Simulate automatic missed" }).click();
  await expect(
    medication(page).getByText("Missed", { exact: true }),
  ).toBeVisible();
  await expect(medication(page).getByRole("button")).toHaveCount(0);
  await page.getByRole("button", { name: "Reset reminders" }).click();
  await medication(page)
    .getByRole("button", { name: "Missed", exact: true })
    .click();
  await expect(
    medication(page).getByText("Missed", { exact: true }),
  ).toBeVisible();
});

test("appointment requires explicit confirmation and supports cancellation", async ({
  page,
}) => {
  await page.goto(demo);
  await page.getByRole("button", { name: "Book an appointment" }).click();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Your message", { exact: true })).toBeDisabled();
  await expect(page.getByText(/Sample appointment confirmed/)).toHaveCount(0);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByText("Cancelled. No appointment was booked."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Book an appointment" }).click();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText(/Sample appointment confirmed/)).toBeVisible();
});

test("failed conversation can retry without duplicating the user message", async ({
  page,
}) => {
  await page.goto(demo);
  await expect(medication(page)).toBeVisible();
  await page.getByText("Demo controls", { exact: true }).click();
  await page.getByRole("button", { name: "Fail next request" }).click();
  await page.getByLabel("Your message", { exact: true }).fill("Hello there");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Retry message" }).click();
  await expect(
    page.getByText(
      "Hello. Would you like to review an appointment or check your reminders?",
    ),
  ).toBeVisible();
  await expect(page.getByText("Hello there", { exact: true })).toHaveCount(1);
});

test("live 409 refreshes to automatic missed and never shows false Taken", async ({
  page,
}) => {
  let status = "sent";
  let posts = 0;
  await page.route("**/notifications", (route) =>
    route.fulfill({
      json: [
        {
          id: "notice-1",
          kind: "medication_reminder",
          payload: { ...fixture, status },
        },
      ],
    }),
  );
  await page.route(
    "**/api/v1/medication-reminders/dose-1/taken",
    async (route) => {
      posts++;
      expect(route.request().postData()).toBeNull();
      status = "missed";
      await route.fulfill({ status: 409, json: {} });
    },
  );
  await page.goto(live);
  await expect(medication(page).locator("time")).toContainText("8:00 AM PDT");
  await medication(page)
    .getByRole("button", { name: "Taken", exact: true })
    .click();
  await expect(
    medication(page).getByText("Missed", { exact: true }),
  ).toBeVisible();
  await expect(medication(page).getByRole("button")).toHaveCount(0);
  expect(posts).toBe(1);
});

test("live reminder failure keeps buttons for retry and prevents duplicate requests", async ({
  page,
}) => {
  let status = "sent";
  let posts = 0;
  await page.route("**/notifications", (route) =>
    route.fulfill({
      json: [
        {
          id: "notice-1",
          kind: "medication_reminder",
          payload: { ...fixture, status },
        },
      ],
    }),
  );
  await page.route(
    "**/api/v1/medication-reminders/dose-1/taken",
    async (route) => {
      posts++;
      await new Promise((resolve) => setTimeout(resolve, 200));
      if (posts === 1) return route.fulfill({ status: 500, json: {} });
      status = "taken";
      await route.fulfill({ json: { ...fixture, status } });
    },
  );
  await page.goto(live);
  const taken = medication(page).getByRole("button", {
    name: "Taken",
    exact: true,
  });
  await taken.click();
  await expect(
    medication(page).getByRole("button", { name: "Missed", exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText("couldn't complete");
  await expect(taken).toBeEnabled();
  await taken.click();
  await expect(
    medication(page).getByText("Taken", { exact: true }),
  ).toBeVisible();
  expect(posts).toBe(2);
});

test("live missing API never silently uses sample data", async ({ page }) => {
  await page.route("**/notifications", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.route("**/api/v1/ai/process", (route) =>
    route.fulfill({ status: 500, json: {} }),
  );
  await page.goto(live);
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(medication(page)).toHaveCount(0);
  await expect(page.getByText("Demo mode", { exact: true })).toHaveCount(0);
  await page
    .getByLabel("Your message", { exact: true })
    .fill("Book an appointment");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Retry message" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(0);
});

test("only sent medication reminders have buttons", async ({ page }) => {
  const statuses = [
    "scheduled",
    "sent",
    "taken",
    "missed",
    "cancelled",
    "failed",
  ];
  await page.route("**/notifications", (route) =>
    route.fulfill({
      json: statuses.map((status) => ({
        id: `notice-${status}`,
        kind: "medication_reminder",
        payload: { ...fixture, id: `dose-${status}`, status },
      })),
    }),
  );
  await page.goto(live);
  await expect(medication(page)).toHaveCount(6);
  await expect(
    page.getByRole("button", { name: "Taken", exact: true }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "Missed", exact: true }),
  ).toHaveCount(1);
});

test("an expired proposal cannot be confirmed", async ({ page }) => {
  await page.route("**/notifications", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/ai/process", (route) =>
    route.fulfill({
      json: {
        reply: "Please review.",
        pending_action: {
          id: "expired",
          summary: "Old appointment",
          expires_at: "2020-01-01T00:00:00Z",
        },
      },
    }),
  );
  await page.goto(live);
  await page.getByLabel("Your message", { exact: true }).fill("Book a visit");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText(/proposal has expired/)).toBeVisible();
});

for (const width of [1440, 390, 320]) {
  test(`layout and larger text fit at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(demo);
    await expect(medication(page)).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`companion-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Larger text" }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "Book an appointment" }).click();
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Confirm", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`confirmation-large-${width}.png`),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
