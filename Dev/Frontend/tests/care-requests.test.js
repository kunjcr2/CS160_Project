import test from "node:test";
import assert from "node:assert/strict";
import { createDemoCareRequests } from "../src/models/careRequests.js";
import { createApi, normalizeReply } from "../src/models/api.js";

function setup() {
  let clock = Date.parse("2026-11-17T18:00:00Z");
  const medications = [
    { id: "available", name: "Sample medication", dosage: "10 mg", refills_remaining: 2 },
    { id: "none", refills_remaining: 0 }, { id: "unknown" },
    { id: "stopped", refills_remaining: 2, stopped_at: "2026-11-01" },
  ];
  return { api: createDemoCareRequests({ settle: async () => {}, medications, now: () => clock }),
    advance: () => { clock += 300001; } };
}

test("live adapters enable verified capabilities but do not invent a Help-history endpoint", () => {
  let calls = 0;
  const api = createApi({ fetchImpl: async () => { calls++; throw new Error("Unexpected network"); } });
  assert.deepEqual(api.careRequests, { help: true, refills: true, queue: true, helpHistory: false });
  assert.equal(api.listHelpRequests, undefined);
  assert.equal(calls, 0);
});

test("AI Help and refill intents never become invented persisted actions", () => {
  for (const kind of ["human_help", "refill"]) {
    const result = normalizeReply({ reply: "Let us review your request.", proposal: { kind, summary: "Need assistance" } });
    assert.equal(result.proposal, null);
    assert.match(result.notice, /No request has been submitted/);
  }
});

test("demo help shares only the reviewed summary; cancel does not enqueue; confirm is idempotent", async () => {
  const { api } = setup();
  const cancelled = await api.proposeHumanHelp("older-1", "  Help with the app  ");
  assert.equal((await api.listHelpRequests("older-1")).length, 0);
  await api.resolveCareRequest(cancelled.id, "cancel");
  assert.equal((await api.listHelpRequests("older-1")).length, 0);
  await assert.rejects(api.resolveCareRequest(cancelled.id, "confirm"));
  const proposal = await api.proposeHumanHelp("older-1", "  Help with the app  ");
  await api.resolveCareRequest(proposal.id, "confirm");
  await api.resolveCareRequest(proposal.id, "confirm");
  const records = await api.listHelpRequests("older-1");
  assert.equal(records.length, 1);
  assert.equal(records[0].summary, "Help with the app");
  assert.equal(records[0].status, "waiting");
  assert.equal("transcript" in records[0], false);
  assert.equal((await api.listHelpRequests("unrelated-user")).length, 0);
});

test("demo accepts optional Help summary, rejects overlong and expired confirmation", async () => {
  const { api, advance } = setup();
  await api.proposeHumanHelp("u", "");
  await assert.rejects(api.proposeHumanHelp("u", "x".repeat(301)));
  const action = await api.proposeHumanHelp("u", "x".repeat(300));
  advance();
  await assert.rejects(api.resolveCareRequest(action.id, "confirm"), (error) => error.status === 410);
  await api.resolveCareRequest(action.id, "cancel");
  assert.equal((await api.listHelpRequests("u")).length, 0);
});

test("refill demo rejects unknown, exhausted or stopped medications and never claims approval", async () => {
  const { api } = setup();
  for (const id of ["missing", "none", "unknown", "stopped"]) await assert.rejects(api.proposeRefill("u", id));
  const action = await api.proposeRefill("u", "available");
  assert.equal((await api.listRefillRequests("u")).length, 0);
  const result = await api.resolveCareRequest(action.id, "confirm");
  assert.match(result.message, /No pharmacy was contacted or refill approved/);
  assert.equal((await api.listRefillRequests("u"))[0].status, "submitted");
  await assert.rejects(api.proposeRefill("u", "available"));
});

test("two demo proposals cannot produce duplicate refill records", async () => {
  const { api } = setup();
  const first = await api.proposeRefill("u", "available");
  const second = await api.proposeRefill("u", "available");
  await api.resolveCareRequest(first.id, "confirm");
  await assert.rejects(api.resolveCareRequest(second.id, "confirm"), (error) => error.status === 409);
  await api.resolveCareRequest(first.id, "confirm");
  assert.equal((await api.listRefillRequests("u")).length, 1);
});

test("queue accepts only waiting-to-in-progress-to-resolved and rejects stale updates", async () => {
  const { api } = setup();
  const row = (await api.listSupportQueue())[0];
  await assert.rejects(api.updateSupportRequest(row.id, "waiting", "resolved"));
  await api.updateSupportRequest(row.id, "waiting", "in_progress");
  await assert.rejects(api.updateSupportRequest(row.id, "waiting", "in_progress"), (error) => error.status === 409);
  await api.updateSupportRequest(row.id, "in_progress", "resolved");
  await assert.rejects(api.updateSupportRequest(row.id, "resolved", "waiting"));
  const final = (await api.listSupportQueue())[0];
  assert.equal(final.status, "resolved");
  final.summary = "mutated copy";
  assert.notEqual((await api.listSupportQueue())[0].summary, "mutated copy");
});
