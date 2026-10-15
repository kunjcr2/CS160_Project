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
  assert.throws(
    () =>
      normalizeNotifications([{ ...reminder, kind: "medication_reminder" }]),
    /reminder ID/,
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

test("SSE reconnects trigger snapshot recovery and subscriptions close", () => {
  const Original = globalThis.EventSource;
  let source;
  globalThis.EventSource = class {
    constructor(path, options) {
      this.path = path;
      this.options = options;
      this.events = {};
      source = this;
    }
    addEventListener(name, fn) {
      this.events[name] = fn;
    }
    close() {
      this.closed = true;
    }
  };
  try {
    let refreshes = 0;
    const states = [];
    const close = createApi({ streamPath: "/notifications/stream" }).subscribe(
      () => refreshes++,
      (value) => states.push(value),
    );
    source.onopen();
    source.onmessage();
    source.onerror();
    source.onopen();
    source.events.reminder_updated();
    assert.equal(refreshes, 4);
    assert.deepEqual(states, [
      "connecting",
      "connected",
      "reconnecting",
      "connected",
    ]);
    assert.equal(source.options.withCredentials, true);
    close();
    assert.equal(source.closed, true);
  } finally {
    globalThis.EventSource = Original;
  }
});

test("appointment OK uses the notification ID and verifies refreshed status", async () => {
  const calls = [];
  const appointment = {
    ...reminder,
    kind: "appointment_reminder",
    notification_id: "notice-2",
  };
  const api = createApi({
    fetchImpl: async (path) => {
      calls.push(path);
      return path.endsWith("/ack")
        ? json({})
        : json([
            {
              id: "notice-2",
              kind: "appointment_reminder",
              payload: { ...reminder, status: "acknowledged" },
            },
          ]);
    },
  });
  const updated = await api.answerReminder(appointment, "acknowledged");
  assert.deepEqual(calls, ["/notifications/notice-2/ack", "/notifications"]);
  assert.equal(updated.status, "acknowledged");
});
