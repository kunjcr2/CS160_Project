import test from "node:test";
import assert from "node:assert/strict";
import { createApi } from "../src/models/api.js";

const json = (value, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

test("overlapping session restores (StrictMode) share a refresh", async () => {
  const gate = deferred();
  let refreshes = 0;
  const api = createApi({
    fetchImpl: async (path) => {
      if (path.endsWith("/refresh")) {
        refreshes++;
        await gate.promise;
        return json({ access_token: "new" });
      }
      return json({ id: "adult-1" });
    },
  });
  const first = api.restoreSession();
  const second = api.restoreSession();
  gate.resolve();
  assert.deepEqual(await Promise.all([first, second]), [
    { id: "adult-1" }, { id: "adult-1" },
  ]);
  assert.equal(refreshes, 1);
});

test("a late old-token 401 reuses the token that already refreshed", async () => {
  const lateResponse = deferred();
  let oldRequests = 0;
  let refreshes = 0;
  const api = createApi({
    getAccessToken: () => "old",
    fetchImpl: async (path, options) => {
      if (path.endsWith("/refresh")) {
        refreshes++;
        return json({ access_token: "new" });
      }
      if (options.headers.Authorization === "Bearer old") {
        if (++oldRequests === 2) await lateResponse.promise;
        return json({}, 401);
      }
      assert.equal(options.headers.Authorization, "Bearer new");
      return json([]);
    },
  });
  const first = api.listNotifications();
  const second = api.listNotifications();
  await first;
  lateResponse.resolve();
  await second;
  assert.equal(refreshes, 1);
});

test("temporary refresh failures preserve the session and allow a later retry", async () => {
  for (const failure of ["network", "server"]) {
    let expired = 0;
    let refreshes = 0;
    const api = createApi({
      getAccessToken: () => "old",
      onUnauthorized: () => expired++,
      fetchImpl: async (path, options) => {
        if (path.endsWith("/refresh")) {
          if (++refreshes === 1) {
            if (failure === "network") throw new TypeError("Offline");
            return json({}, 503);
          }
          return json({ access_token: "new" });
        }
        return options.headers.Authorization === "Bearer new"
          ? json([]) : json({}, 401);
      },
    });
    await assert.rejects(api.listNotifications());
    assert.equal(expired, 0);
    assert.deepEqual(await api.listNotifications(), []);
    assert.equal(refreshes, 2);
  }
});

test("shared rejected refresh notifies session expiry only once", async () => {
  const gate = deferred();
  let expired = 0;
  let refreshes = 0;
  const api = createApi({
    getAccessToken: () => "old",
    onUnauthorized: () => expired++,
    fetchImpl: async (path) => {
      if (path.endsWith("/refresh")) {
        refreshes++;
        await gate.promise;
      }
      return json({}, 401);
    },
  });
  const requests = Promise.allSettled([
    api.listNotifications(), api.listNotifications(),
  ]);
  gate.resolve();
  const results = await requests;
  assert.ok(results.every((result) => result.status === "rejected"));
  assert.equal(refreshes, 1);
  assert.equal(expired, 1);
});

test("cancelling a caller during shared refresh stops its retry, not other callers", async () => {
  const started = deferred();
  const gate = deferred();
  const cancel = new AbortController();
  let retries = 0;
  const api = createApi({
    getAccessToken: () => "old",
    fetchImpl: async (path, options) => {
      if (path.endsWith("/refresh")) {
        started.resolve();
        await gate.promise;
        return json({ access_token: "new" });
      }
      if (options.headers.Authorization === "Bearer old") return json({}, 401);
      retries++;
      return json([]);
    },
  });
  const results = Promise.allSettled([
    api.listNotifications(cancel.signal), api.listNotifications(),
  ]);
  await started.promise;
  cancel.abort();
  gate.resolve();
  const [cancelled, other] = await results;
  assert.equal(cancelled.status, "rejected");
  assert.equal(cancelled.reason.name, "AbortError");
  assert.equal(other.status, "fulfilled");
  assert.equal(retries, 1);
});

test("a response from before logout cannot refresh or restore the old token", async () => {
  const gate = deferred();
  let featureCalls = 0;
  let refreshes = 0;
  const api = createApi({
    getAccessToken: () => "old",
    fetchImpl: async (path, options) => {
      if (path.endsWith("/logout")) return new Response(null, { status: 204 });
      if (path.endsWith("/refresh")) { refreshes++; return json({ access_token: "new" }); }
      if (++featureCalls === 1) { await gate.promise; return json({}, 401); }
      assert.equal(options.headers.Authorization, undefined);
      return json([], 401);
    },
  });
  const rejected = assert.rejects(api.listNotifications(), (error) => error.code === "session_changed");
  await api.signOut();
  gate.resolve();
  await rejected;
  await assert.rejects(api.listNotifications(), (error) => error.status === 401);
  assert.equal(refreshes, 0);
});

test("a late previous-session response cannot sign out a newly signed-in user", async () => {
  const gate = deferred();
  let expired = 0;
  const api = createApi({
    getAccessToken: () => "old",
    onUnauthorized: () => expired++,
    fetchImpl: async (path, options) => {
      if (path.endsWith("/login")) return json({ access_token: "new-user" });
      if (path.endsWith("/me")) return json({ id: "new-user" });
      if (options.headers.Authorization === "Bearer old") {
        await gate.promise;
        return json({}, 401);
      }
      assert.equal(options.headers.Authorization, "Bearer new-user");
      return json([]);
    },
  });
  const rejected = assert.rejects(api.listNotifications(), (error) => error.code === "session_changed");
  await api.signIn("login", { email: "test@example.com", password: "test" });
  gate.resolve();
  await rejected;
  assert.deepEqual(await api.listNotifications(), []);
  assert.equal(expired, 0);
});
