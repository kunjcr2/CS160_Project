import { test, expect } from "./fixtures.js";

const live = "http://127.0.0.1:5181";
const user = {
  id: "adult-1",
  role: "older_adult",
  display_name: "Margaret",
  timezone: "America/New_York",
};

async function mockSession(page, profile = user) {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "test-token" } }),
  );
  await page.route("**/api/v1/users/me", (route) =>
    route.fulfill({ json: profile }),
  );
  await page.route("**/api/v1/notifications", (route) =>
    route.fulfill({ json: [] }),
  );
}

async function mockMedia(
  page,
  { denied = false, blockedPlayback = false } = {},
) {
  await page.addInitScript(
    ({ denied, blockedPlayback }) => {
      window.mediaTest = { stopped: 0, played: 0, paused: 0, revoked: 0 };
      const originalRevoke = URL.revokeObjectURL.bind(URL);
      URL.revokeObjectURL = (url) => {
        window.mediaTest.revoked++;
        originalRevoke(url);
      };
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        value: async () => {
          if (denied) throw new DOMException("Denied", "NotAllowedError");
          return {
            getTracks: () => [
              {
                stop: () => {
                  window.mediaTest.stopped++;
                },
              },
            ],
          };
        },
      });
      window.MediaRecorder = class {
        static isTypeSupported(type) {
          return type === "audio/webm;codecs=opus";
        }
        constructor(stream, options) {
          this.mimeType = options.mimeType;
          this.state = "inactive";
        }
        start() {
          this.state = "recording";
        }
        stop() {
          this.state = "inactive";
          setTimeout(() => {
            this.ondataavailable?.({
              data: new Blob(["recorded-audio"], { type: this.mimeType }),
            });
            this.onstop?.();
          }, 0);
        }
      };
      window.Audio = class {
        async play() {
          if (blockedPlayback)
            throw new DOMException("Blocked", "NotAllowedError");
          window.mediaTest.played++;
        }
        pause() {
          window.mediaTest.paused++;
        }
        removeAttribute() {}
        load() {}
      };
    },
    { denied, blockedPlayback },
  );
}

test("pairing login, Bearer requests and logout clear the conversation", async ({
  page,
}) => {
  await mockSession(page);
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { detail: "Not signed in." } }),
  );
  await page.route("**/api/v1/auth/pair", (route) => {
    expect(route.request().postDataJSON()).toEqual({ code: "12345678" });
    return route.fulfill({ json: { access_token: "paired-token" } });
  });
  await page.route("**/api/v1/users/me", (route) => {
    expect(route.request().headers().authorization).toBe("Bearer paired-token");
    return route.fulfill({ json: user });
  });
  await page.route("**/api/v1/auth/logout", (route) =>
    route.fulfill({ status: 204 }),
  );
  await page.goto(live);
  await page.getByLabel("Pairing code", { exact: true }).fill("12345678");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Margaret", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("log")).toHaveCount(0);
});

test("record, transcribe, review, send and play a reply with no false confirmation", async ({
  page,
}, testInfo) => {
  await mockSession(page);
  await mockMedia(page);
  let sends = 0;
  await page.route("**/api/v1/ai/transcribe", async (route) => {
    expect(route.request().headers()["content-type"]).toContain(
      "multipart/form-data; boundary=",
    );
    expect(route.request().postData()).toContain('name="audio"');
    expect(route.request().postData()).toContain("recorded-audio");
    await route.fulfill({ json: { text: "Book a visit tomorrow." } });
  });
  await page.route("**/api/v1/ai/process", (route) => {
    sends++;
    expect(route.request().postDataJSON()).toEqual({
      text: "Book a visit tomorrow.",
      language: "en",
    });
    return route.fulfill({
      json: {
        reply: "Let's find a doctor.",
        proposal: { kind: "appointment", doctor: null, date_hint: "tomorrow" },
      },
    });
  });
  await page.route("**/api/v1/ai/tts", (route) =>
    route.fulfill({ contentType: "audio/mpeg", body: Buffer.from([1, 2, 3]) }),
  );
  await page.goto(live);
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await expect(page.getByText(/Recording 0s/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Send", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "Book a visit tomorrow.",
  );
  expect(sends).toBe(0);
  expect(await page.evaluate(() => window.mediaTest.stopped)).toBeGreaterThan(
    0,
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText("Let's find a doctor.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/No appointment or reminder has been saved/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Play reply", exact: true }).click();
  await expect(page.getByText("Responding...", { exact: true })).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("voice-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Stop reply", exact: true }).click();
  expect(await page.evaluate(() => window.mediaTest.revoked)).toBe(1);
  expect(sends).toBe(1);
});

test("microphone denial leaves typing available", async ({ page }) => {
  await mockSession(page);
  await mockMedia(page, { denied: true });
  await page.goto(live);
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Microphone access was denied",
  );
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
});

test("cancel recording discards audio and keeps existing draft", async ({
  page,
}) => {
  await mockSession(page);
  await mockMedia(page);
  let uploads = 0;
  await page.route("**/api/v1/ai/transcribe", (route) => {
    uploads++;
    return route.fulfill({ json: { text: "Should not appear" } });
  });
  await page.goto(live);
  await page.getByLabel("Your message", { exact: true }).fill("Existing draft");
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Cancel recording", exact: true })
    .click();
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "Existing draft",
  );
  await expect(
    page.getByRole("button", { name: "Record message", exact: true }),
  ).toBeEnabled();
  expect(uploads).toBe(0);
  expect(await page.evaluate(() => window.mediaTest.stopped)).toBeGreaterThan(
    0,
  );
});

test("failed transcription can be retried and does not erase a typed draft", async ({
  page,
}) => {
  await mockSession(page);
  await mockMedia(page);
  let uploads = 0;
  await page.route("**/api/v1/ai/transcribe", (route) => {
    uploads++;
    return uploads === 1
      ? route.fulfill({
          status: 503,
          json: { detail: "Speech transcription failed" },
        })
      : route.fulfill({ json: { text: "New words" } });
  });
  await page.goto(live);
  await page.getByLabel("Your message", { exact: true }).fill("Existing draft");
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Speech transcription failed",
  );
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "Existing draft\nNew words",
  );
});

test("blocked automatic playback keeps text visible and permits manual retry", async ({
  page,
}) => {
  await mockSession(page);
  await mockMedia(page, { blockedPlayback: true });
  await page.route("**/api/v1/ai/process", (route) =>
    route.fulfill({ json: { reply: "Hello Margaret.", proposal: null } }),
  );
  await page.route("**/api/v1/ai/tts", (route) =>
    route.fulfill({ contentType: "audio/mpeg", body: Buffer.from([1, 2, 3]) }),
  );
  await page.goto(live);
  await page.getByLabel("Read replies aloud").check();
  await page.getByLabel("Your message", { exact: true }).fill("Hello");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "browser blocked playback",
  );
  await expect(
    page.getByText("Hello Margaret.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Play reply", exact: true }),
  ).toBeEnabled();
  expect(await page.evaluate(() => window.mediaTest.revoked)).toBe(1);
});

test("notification polling updates sent to missed and uses profile timezone", async ({
  page,
}) => {
  await mockSession(page);
  let status = "sent";
  await page.route("**/api/v1/notifications", (route) => {
    return route.fulfill({
      json: [
        {
          id: "dose-1",
          kind: "medication_reminder",
          due_at: "2026-10-13T15:00:00Z",
          message: "Medication reminder",
          status,
        },
      ],
    });
  });
  await page.clock.install();
  await page.goto(live);
  await expect(
    page.getByRole("button", { name: "Taken", exact: true }),
  ).toBeVisible();
  await expect(page.locator("time")).toContainText("11:00 AM EDT");
  status = "missed";
  await page.clock.fastForward(21000);
  await expect(page.getByText("Missed", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Taken", exact: true }),
  ).toHaveCount(0);
});

test("caregiver cannot press medication buttons", async ({ page }) => {
  await mockSession(page, { ...user, role: "caregiver" });
  await page.route("**/api/v1/notifications", (route) =>
    route.fulfill({
      json: [
        {
          id: "dose-1",
          kind: "medication_reminder",
          due_at: "2026-10-13T15:00:00Z",
          message: "Medication reminder",
          status: "sent",
        },
      ],
    }),
  );
  await page.goto(live);
  await expect(
    page.getByRole("article", { name: "Medication reminder", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Taken", exact: true }),
  ).toHaveCount(0);
});

test("recording automatically stops after 60 seconds", async ({ page }) => {
  await mockSession(page);
  await mockMedia(page);
  await page.route("**/api/v1/ai/transcribe", (route) =>
    route.fulfill({ json: { text: "A short transcript" } }),
  );
  await page.clock.install();
  await page.goto(live);
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Stop recording", exact: true }),
  ).toBeVisible();
  await page.clock.fastForward(61000);
  await page.clock.runFor(10);
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "A short transcript",
  );
  await expect(
    page.getByRole("button", { name: "Stop recording", exact: true }),
  ).toHaveCount(0);
});

test("cancelling transcription ignores a late response", async ({ page }) => {
  await mockSession(page);
  await mockMedia(page);
  let respond;
  const gate = new Promise((resolve) => {
    respond = resolve;
  });
  await page.route("**/api/v1/ai/transcribe", async (route) => {
    await gate;
    await route
      .fulfill({ json: { text: "Discard this result" } })
      .catch(() => {});
  });
  await page.goto(live);
  await page
    .getByRole("button", { name: "Record message", exact: true })
    .click();
  const upload = page.waitForRequest("**/api/v1/ai/transcribe");
  await page
    .getByRole("button", { name: "Stop recording", exact: true })
    .click();
  await upload;
  await expect(
    page.getByText("Transcribing...", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Cancel recording", exact: true })
    .click();
  respond();
  await expect(
    page.getByRole("button", { name: "Record message", exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "",
  );
});

test("failed action result in HTTP 200 is not displayed as a booking success", async ({
  page,
}) => {
  await mockSession(page);
  await page.route("**/api/v1/ai/process", (route) =>
    route.fulfill({
      json: {
        reply: "Please review.",
        pending_action: {
          id: "a1",
          summary_text: "Book appointment",
          expires_at: "2099-01-01T00:00:00Z",
        },
      },
    }),
  );
  await page.route("**/api/v1/actions/a1/confirm", (route) =>
    route.fulfill({
      json: {
        action: { id: "a1", status: "failed" },
        message: "This slot is no longer available.",
      },
    }),
  );
  await page.goto(live);
  await page
    .getByLabel("Your message", { exact: true })
    .fill("Book an appointment");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "This slot is no longer available.",
  );
  await expect(
    page.getByRole("button", { name: "Confirm", exact: true }),
  ).toHaveCount(0);
});

for (const width of [390, 320]) {
  test(`live voice controls fit at ${width}px`, async ({ page }, testInfo) => {
    await mockSession(page);
    await mockMedia(page);
    await page.setViewportSize({ width, height: 900 });
    await page.goto(live);
    await page.getByRole("button", { name: "Larger text" }).click();
    await page
      .getByRole("button", { name: "Record message", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Stop recording", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`voice-mobile-${width}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Cancel recording", exact: true })
      .click();
  });
}
