import test from "node:test";
import assert from "node:assert/strict";
import { createApi } from "../src/models/api.js";
import { normalizeAssistance, normalizeRefills } from "../src/models/requestApi.js";
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
const action = (type) => ({ id: "a1", action_type: type, status: "proposed", summary_text: "Review this request?", expires_at: "2027-01-01T00:00:00Z" });
const assistance = { id: "r1", older_adult_id: "u1", older_adult_name: "Maggie", summary: null, status: "open", assigned_to_name: null, created_at: "2026-11-19T18:00:00Z", resolved_at: null };
const refill = { id: "r1", medication: { id: "m1", name: "Lisinopril", dosage: "10 mg", refills_remaining: 1 }, status: "requested", status_message: "Your refill was requested.", created_at: "2026-11-19T18:00:00Z" };

test("PR38 proposals preserve payloads and never execute during creation", async () => {
  const calls = [];
  const api = createApi({ getAccessToken: () => "token", fetchImpl: async (path, options) => {
    const body = JSON.parse(options.body); calls.push({ path, options, body }); return json(action(body.action_type));
  } });
  await api.proposeHumanHelp("u1", "  Need help  ", "repeated_failures");
  await api.proposeHumanHelp("u1", "");
  await api.proposeRefill("u1", "m1");
  await api.proposeCancellation("visit1");
  await api.proposeReschedule("visit1", "opaque:slot/2");
  assert.deepEqual(calls.map((x) => x.body), [
    { action_type: "request_help", payload: { older_adult_id: "u1", summary: "Need help", reason: "repeated_failures" } },
    { action_type: "request_help", payload: { older_adult_id: "u1", summary: "", reason: "user_request" } },
    { action_type: "request_refill", payload: { older_adult_id: "u1", medication_id: "m1" } },
    { action_type: "cancel_appointment", payload: { appointment_id: "visit1" } },
    { action_type: "reschedule_appointment", payload: { appointment_id: "visit1", slot_id: "opaque:slot/2" } },
  ]);
  for (const call of calls) {
    assert.equal(call.path, "/api/v1/actions"); assert.equal(call.options.method, "POST");
    assert.equal(call.options.headers.Authorization, "Bearer token");
  }
  await assert.rejects(api.proposeHumanHelp("u1", "x".repeat(301)));
  await assert.rejects(api.proposeHumanHelp("u1", "ok", "invented_reason"));
  assert.equal(calls.length, 5);
});

test("mismatched proposal types are rejected before showing a confirmation", async () => {
  const api = createApi({ fetchImpl: async () => json(action("request_help")) });
  await assert.rejects(api.proposeRefill("u", "m"), /incomplete/);
});

test("confirmation validates action type, failed status, and saved result ID before announcing success", async () => {
  for (const [type, key] of [["request_help", "assistance_request_id"], ["request_refill", "refill_request_id"], ["cancel_appointment", "appointment_id"], ["reschedule_appointment", "appointment_id"]]) {
    let result = { ...action(type), status: "executed", result: {} };
    const api = createApi({ fetchImpl: async () => json({ action: result, message: "Outcome" }) });
    await assert.rejects(api.resolveAction("a1", "confirm", type), /verify/);
    result.result[key] = "saved-id";
    assert.equal((await api.resolveAction("a1", "confirm", type)).data[key], "saved-id");
    result.status = "failed";
    await assert.rejects(api.resolveAction("a1", "confirm", type), (error) => error.code === "action_failed");
    result = { ...action("send_care_message"), status: "executed" };
    await assert.rejects(api.resolveAction("a1", "confirm", type), /verify/);
  }
});

test("queue adapters normalize nullable summary and display fields, filter resolved and encode PATCH", async () => {
  const calls = [];
  const api = createApi({ getAccessToken: () => "agent", fetchImpl: async (path, options) => {
    calls.push({ path, options });
    return json(options.method === "PATCH" ? { ...assistance, id: "r/1", status: "in_progress", assigned_to_name: "Agent" }
      : [assistance, { ...assistance, id: "done", status: "resolved" }]);
  } });
  const rows = await api.listSupportQueue("agent1");
  assert.equal(rows.length, 1); assert.equal(rows[0].display_name, "Maggie"); assert.equal(rows[0].summary, null);
  await api.updateSupportRequest("r/1", "open", "in_progress");
  assert.equal(calls[1].path, "/api/v1/assistance/r%2F1");
  assert.deepEqual(JSON.parse(calls[1].options.body), { status: "in_progress" });
  assert.equal(calls[1].options.headers.Authorization, "Bearer agent");
  assert.throws(() => normalizeAssistance({ ...assistance, status: "waiting" }));
});

test("stale claims and mismatched PATCH responses are not treated as successful updates", async () => {
  const api = createApi({ fetchImpl: async () => json({ detail: { code: "in_progress", message: "Already claimed." } }, 409) });
  await assert.rejects(api.updateSupportRequest("r1", "open", "in_progress"), (error) => error.status === 409 && error.message === "Already claimed.");
  const wrong = createApi({ fetchImpl: async () => json({ ...assistance, id: "wrong", status: "in_progress" }) });
  await assert.rejects(wrong.updateSupportRequest("r1", "open", "in_progress"));
});

test("refill list maps nested medication and status message without treating unknown states as ready", async () => {
  let path;
  const api = createApi({ fetchImpl: async (url) => { path = url; return json([refill]); } });
  const rows = await api.listRefillRequests("u/1");
  assert.equal(path, "/api/v1/older-adults/u%2F1/refills");
  assert.equal(rows[0].medication_id, "m1"); assert.equal(rows[0].medication_name, "Lisinopril");
  assert.equal(rows[0].status_message, refill.status_message);
  assert.throws(() => normalizeRefills([{ ...refill, status: "submitted" }]));
  assert.throws(() => normalizeRefills([{ ...refill, medication: null }]));
});

test("conversation carries unclear-turn state back to PR31 and preserves a Help suggestion", async () => {
  let body;
  const api = createApi({ fetchImpl: async (_url, options) => {
    body = JSON.parse(options.body); return json({ reply: "Would you like help?", unclear_turns: 3, offer_human_help: true, proposal: null });
  } });
  const reply = await api.converse("Try again", null, 2);
  assert.deepEqual(body, { text: "Try again", language: "en", unclear_turns: 2 });
  assert.equal(reply.offerHumanHelp, true); assert.equal(reply.unclearTurns, 3); assert.equal(reply.proposal, null);
});
