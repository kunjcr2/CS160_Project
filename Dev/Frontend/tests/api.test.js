import test from "node:test";
import assert from "node:assert/strict";
import { createApi, normalizeReply } from "../src/models/api.js";
import {
  normalizeNotifications,
  mergeReminders,
  formatWhen,
} from "../src/models/reminders.js";

const reminder = {
  id: "dose-1",
  medication_name: "Lisinopril",
  dosage: "10 mg",
  due_at: "2026-10-13T15:00:00Z",
  status: "sent",
  message: "Time to take your Lisinopril, 10 mg.",
};
const json = (value, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });

test("notification IDs stay separate from medication reminder IDs", () => {
  const [row] = normalizeNotifications([
    { id: "notice-1", kind: "medication_reminder", payload: reminder },
  ]);
  assert.equal(row.id, "dose-1");
  assert.equal(row.notification_id, "notice-1");
  assert.equal(
    normalizeNotifications([{ ...reminder, kind: "medication_reminder" }])[0]
      .id,
    "dose-1",
  );
});

test("updated reminders replace existing rows without duplicate banners", () => {
  const current = [{ ...reminder, kind: "medication_reminder" }];
  const next = mergeReminders(current, [{ ...current[0], status: "missed" }]);
  assert.equal(next.length, 1);
  assert.equal(next[0].status, "missed");
});

test("UTC times respect local zones and daylight saving", () => {
  assert.match(
    formatWhen("2026-10-13T15:00:00Z", "America/Los_Angeles"),
    /8:00 AM PDT/,
  );
  assert.match(
    formatWhen("2026-12-13T15:00:00Z", "America/Los_Angeles"),
    /7:00 AM PST/,
  );
  assert.equal(formatWhen("bad date"), "Time unavailable");
});

test("Taken and Missed POST without a request body using the reminder ID", async () => {
  for (const answer of ["taken", "missed"]) {
    let call;
    const api = createApi({
      fetchImpl: async (...args) => {
        call = args;
        return json({ ...reminder, status: answer });
      },
    });
    const row = await api.answerReminder(
      { ...reminder, kind: "medication_reminder", notification_id: "notice-1" },
      answer,
    );
    assert.equal(call[0], `/api/v1/medication-reminders/dose-1/${answer}`);
    assert.equal(call[1].method, "POST");
    assert.equal(call[1].body, undefined);
    assert.equal(row.status, answer);
  }
});

test("errors never become fabricated successful reminders", async () => {
  for (const status of [401, 404, 409, 500]) {
    const api = createApi({ fetchImpl: async () => json({}, status) });
    await assert.rejects(
      api.answerReminder({ ...reminder, kind: "medication_reminder" }, "taken"),
      (error) => error.status === status,
    );
  }
});

test("unexpected HTML or a mismatched mutation response is rejected", async () => {
  const html = createApi({
    fetchImpl: async () =>
      new Response("<html/>", { headers: { "content-type": "text/html" } }),
  });
  await assert.rejects(html.listNotifications(), /unexpected response/);
  const mismatch = createApi({
    fetchImpl: async () =>
      json({ ...reminder, id: "other-dose", status: "taken" }),
  });
  await assert.rejects(
    mismatch.answerReminder(
      { ...reminder, kind: "medication_reminder" },
      "taken",
    ),
    /changed/,
  );
});

test("malformed conversation replies and proposals are rejected", () => {
  assert.throws(() => normalizeReply({ reply: {} }), /unreadable/);
  assert.throws(
    () =>
      normalizeReply({
        reply: "Review",
        pending_action: { summary: "Book it" },
      }),
    /incomplete/,
  );
});

test("action success must be explicitly confirmed by the server", async () => {
  const api = createApi({
    fetchImpl: async () => json({ status: "pending", message: "Not done" }),
  });
  await assert.rejects(api.resolveAction("action-1", "confirm"), /verify/);
});

test("polling waits for refresh and subscriptions close", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let refreshes = 0;
  const states = [];
  const close = createApi().subscribe(
    async () => {
      refreshes++;
    },
    (state) => states.push(state),
  );
  t.mock.timers.tick(20000);
  await Promise.resolve();
  assert.equal(refreshes, 1);
  assert.deepEqual(states, ["polling"]);
  close();
  t.mock.timers.tick(60000);
  assert.equal(refreshes, 1);
});

test("appointment OK uses the reminder ID and verifies returned status", async () => {
  const calls = [];
  const appointment = {
    ...reminder,
    kind: "appointment_reminder",
    notification_id: "notice-2",
  };
  const api = createApi({
    fetchImpl: async (path) => {
      calls.push(path);
      return json({
        ...reminder,
        kind: "appointment_reminder",
        status: "acknowledged",
      });
    },
  });
  const updated = await api.answerReminder(appointment, "acknowledged");
  assert.deepEqual(calls, ["/api/v1/appointment-reminders/dose-1/acknowledge"]);
  assert.equal(updated.status, "acknowledged");
});

test("AI intent remains readable but is never treated as a persisted action", () => {
  const result = normalizeReply({
    reply: "Let's find a doctor.",
    proposal: { kind: "appointment", doctor: "Chen", date_hint: "tomorrow" },
  });
  assert.equal(result.proposal, null);
  assert.match(result.notice, /No appointment or reminder has been saved/);
  assert.equal(result.text, "Let's find a doctor.");
});

test("persisted action summary_text and wrapped confirmation are accepted", async () => {
  assert.equal(
    normalizeReply({
      reply: "Review",
      pending_action: { id: "a1", summary_text: "Book visit" },
    }).proposal.summary,
    "Book visit",
  );
  const api = createApi({
    fetchImpl: async () =>
      json({ action: { id: "a1", status: "executed" }, message: "Booked" }),
  });
  assert.equal((await api.resolveAction("a1", "confirm")).status, "executed");
  const failed = createApi({
    fetchImpl: async () =>
      json({
        action: { id: "a1", status: "failed" },
        message: "Slot is unavailable",
      }),
  });
  await assert.rejects(
    failed.resolveAction("a1", "confirm"),
    /Slot is unavailable/,
  );
});

test("medication dose response need not contain a message; structured errors survive", async () => {
  const { message, ...dose } = reminder;
  const api = createApi({
    fetchImpl: async () => json({ ...dose, status: "taken" }),
  });
  const result = await api.answerReminder(
    { ...reminder, kind: "medication_reminder" },
    "taken",
  );
  assert.equal(result.message, message);
  const failed = createApi({
    fetchImpl: async () =>
      json(
        { detail: { code: "too_early", message: "This dose is not due yet." } },
        409,
      ),
  });
  await assert.rejects(
    failed.answerReminder(
      { ...reminder, kind: "medication_reminder" },
      "taken",
    ),
    (error) =>
      error.code === "too_early" &&
      error.message === "This dose is not due yet.",
  );
});

test("speech uses multipart audio and MP3 response without JSON decoding", async () => {
  const calls = [];
  const api = createApi({
    getAccessToken: () => "test-token",
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      return path.endsWith("/transcribe")
        ? json({ text: " Hello " })
        : new Response(new Uint8Array([1, 2, 3]), {
            headers: { "content-type": "audio/mpeg" },
          });
    },
  });
  assert.equal(
    await api.transcribe(new Blob(["audio"], { type: "audio/mp4" })),
    "Hello",
  );
  const [path, options] = calls[0];
  assert.equal(path, "/api/v1/ai/transcribe");
  assert.equal(options.body.get("audio").name, "recording.m4a");
  assert.equal(options.headers["Content-Type"], undefined);
  assert.equal(options.headers.Authorization, "Bearer test-token");
  assert.equal((await api.synthesize("Hello")).type, "audio/mpeg");
  assert.deepEqual(JSON.parse(calls[1][1].body), { text: "Hello" });
});

test("empty/overlong transcripts and non-audio TTS responses fail explicitly", async () => {
  for (const text of ["", " ", "x".repeat(2001)]) {
    const api = createApi({ fetchImpl: async () => json({ text }) });
    await assert.rejects(api.transcribe(new Blob(["audio"])), /speech|long/);
  }
  const api = createApi({
    fetchImpl: async () => json({ reply: "not audio" }),
  });
  await assert.rejects(api.synthesize("Hello"), /unexpected/);
});

test("session refresh supplies Bearer token and logout accepts 204", async () => {
  const calls = [];
  const api = createApi({
    fetchImpl: async (path, options) => {
      calls.push([path, options]);
      if (path.endsWith("/refresh")) return json({ access_token: "fresh" });
      if (path.endsWith("/logout")) return new Response(null, { status: 204 });
      return json({ id: "user-1", role: "older_adult" });
    },
  });
  assert.equal((await api.restoreSession()).id, "user-1");
  assert.equal(calls[1][1].headers.Authorization, "Bearer fresh");
  await api.signOut();
  assert.equal(calls[2][0], "/api/v1/auth/logout");
});

test("concurrent expired requests share one refresh and retry with the new token", async () => {
  let refreshes = 0;
  const api = createApi({
    getAccessToken: () => "old",
    fetchImpl: async (path, options) => {
      if (path.endsWith("/refresh")) {
        refreshes++;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return json({ access_token: "new" });
      }
      return options.headers.Authorization === "Bearer new"
        ? json([])
        : json({}, 401);
    },
  });
  await Promise.all([api.listNotifications(), api.listNotifications()]);
  assert.equal(refreshes, 1);
});

test("failed refresh expires the session without retrying a mutation", async () => {
  let expired = 0;
  let posts = 0;
  const api = createApi({
    getAccessToken: () => "old",
    onUnauthorized: () => expired++,
    fetchImpl: async (path) => {
      if (path.includes("/medication-reminders/")) posts++;
      return json({}, 401);
    },
  });
  await assert.rejects(
    api.answerReminder({ ...reminder, kind: "medication_reminder" }, "taken"),
  );
  assert.equal(posts, 1);
  assert.equal(expired, 1);
});
