import test from "node:test";
import assert from "node:assert/strict";
import { createApi, normalizeAction } from "../src/models/api.js";
import { localDate, addDays } from "../src/models/dates.js";
const json = (value) =>
  new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json" },
  });

test("profile local date crosses UTC midnight and date arithmetic crosses DST", () => {
  assert.equal(
    localDate("America/Los_Angeles", new Date("2026-11-15T02:00:00Z")),
    "2026-11-14",
  );
  assert.equal(
    localDate("Asia/Taipei", new Date("2026-11-15T02:00:00Z")),
    "2026-11-15",
  );
  assert.equal(addDays("2026-10-31", 2), "2026-11-02");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
});

test("only persisted proposed actions with valid expiry become confirmation cards", () => {
  const action = {
    id: "action-1",
    summary_text: "Book this time?",
    status: "proposed",
    expires_at: "2026-11-20T12:00:00Z",
  };
  assert.equal(normalizeAction(action).summary, action.summary_text);
  for (const bad of [
    { ...action, id: "" },
    { ...action, status: "executed" },
    { ...action, expires_at: "bad" },
    { ...action, summary_text: "" },
  ]) {
    assert.throws(() => normalizeAction(bad), /incomplete/);
  }
});

test("slot query encodes identifiers and proposal retains the opaque slot ID", async () => {
  const calls = [];
  const api = createApi({
    getAccessToken: () => "token",
    fetchImpl: async (path, options) => {
      calls.push({ path, options });
      return json(
        path === "/api/v1/actions"
          ? {
              id: "saved",
              summary_text: "Book?",
              status: "proposed",
              expires_at: "2026-12-01T12:00:00Z",
            }
          : [],
      );
    },
  });
  await api.listSlots("provider/&1", "2026-11-20", "2026-11-27");
  const query = new URL(calls[0].path, "http://local").searchParams;
  assert.equal(query.get("provider_id"), "provider/&1");
  assert.equal(query.get("from"), "2026-11-20");
  await api.proposeAppointment("opaque:slot/+1");
  assert.deepEqual(JSON.parse(calls[1].options.body), {
    action_type: "book_appointment",
    payload: { slot_id: "opaque:slot/+1" },
  });
  assert.equal(calls[1].options.headers.Authorization, "Bearer token");
});

test("daily dose response accepts the documented message-free schema and rejects unknown statuses", async () => {
  let status = "sent";
  const api = createApi({
    fetchImpl: async () =>
      json([
        {
          id: "dose-1",
          medication_name: "Metformin",
          dosage: "500 mg",
          due_at: "2026-11-15T02:00:00Z",
          status,
        },
      ]),
  });
  const [dose] = await api.listMedicationReminders("older-1", "2026-11-14");
  assert.equal(dose.message, "Metformin, 500 mg");
  assert.equal(dose.kind, "medication_reminder");
  status = "unknown";
  await assert.rejects(
    api.listMedicationReminders("older-1", "2026-11-14"),
    /incomplete/,
  );
});
