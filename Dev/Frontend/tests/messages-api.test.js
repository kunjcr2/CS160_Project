import test from "node:test";
import assert from "node:assert/strict";
import { createApi } from "../src/models/api.js";
import { normalizeCareMessages } from "../src/models/careMessages.js";
const json = (value) => new Response(JSON.stringify(value), { headers: { "content-type": "application/json" } });
const action = { id: "message-action", action_type: "send_care_message", summary_text: 'I will send Dr. Chen: "Hello". Should I send it?', status: "proposed", expires_at: "2027-01-01T00:00:00Z" };

test("care message proposals use PR34's exact payload and authenticated endpoint", async () => {
  const requests = [];
  const api = createApi({ getAccessToken: () => "token", fetchImpl: async (path, options) => {
    requests.push({ path, options }); return json(action);
  } });
  const result = await api.proposeCareMessage("older-1", "provider-2", "  Hello\nDoctor  ");
  assert.equal(result.summary, action.summary_text);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].path, "/api/v1/actions");
  assert.equal(requests[0].options.headers.Authorization, "Bearer token");
  assert.deepEqual(JSON.parse(requests[0].options.body), { action_type: "send_care_message", payload: { older_adult_id: "older-1", provider_id: "provider-2", body: "Hello\nDoctor" } });
});

test("empty and overlong drafts never create a pending action", async () => {
  let requests = 0;
  const api = createApi({ fetchImpl: async () => { requests++; return json(action); } });
  for (const body of ["", " \n ", "x".repeat(2001)]) await assert.rejects(api.proposeCareMessage("u", "p", body));
  await assert.rejects(api.proposeCareMessage("u", "", "Hello"));
  assert.equal(requests, 0);
  await api.proposeCareMessage("u", "p", "x".repeat(2000));
  assert.equal(requests, 1);
});

test("executed is not sufficient: failed delivery and unverifiable message results are rejected", async () => {
  let data = { ok: false, message_id: "message-1" };
  const api = createApi({ fetchImpl: async () => json({ action: { ...action, status: "executed", result: data }, message: "Delivery could not be completed." }) });
  await assert.rejects(api.resolveAction(action.id, "confirm", "send_care_message"), (error) => error.code === "message_delivery_failed" && error.status === 409);
  for (const invalid of [null, {}, { ok: true }, { ok: true, message_id: "" }]) {
    data = invalid;
    await assert.rejects(api.resolveAction(action.id, "confirm", "send_care_message"), /verify whether/);
  }
  data = { ok: true, message_id: "message-1" };
  assert.equal((await api.resolveAction(action.id, "confirm", "send_care_message")).status, "executed");
});

test("message history validates documented schema, retains failed entries and sorts newest first", async () => {
  const old = { id: "m1", provider: { id: "p1", name: "Dr. Chen" }, body: "First", status: "failed", created_at: "2026-11-15T18:00:00Z" };
  const newer = { ...old, id: "m2", body: "Second", status: "sent", created_at: "2026-11-16T18:00:00Z" };
  const api = createApi({ fetchImpl: async (path) => {
    assert.equal(path, "/api/v1/older-adults/older%2F1/messages"); return json([old, newer]);
  } });
  assert.deepEqual((await api.listCareMessages("older/1")).map((row) => row.id), ["m2", "m1"]);
  for (const bad of [{ ...old, status: "read" }, { ...old, provider: null }, { ...old, created_at: "bad" }]) assert.throws(() => normalizeCareMessages([bad]), /incomplete/);
});
