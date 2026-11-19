import { test, expect } from "./fixtures.js";

const live = "http://127.0.0.1:5181";
const user = { id: "adult-1", role: "older_adult", display_name: "Margaret" };

test("two tabs serialize real cookie rotations with one refresh per tab", async ({ context, page }) => {
  await context.addCookies([{
    name: "refresh_token", value: "rotation-0", domain: "127.0.0.1",
    path: "/api/v1/auth", httpOnly: true, sameSite: "Lax",
  }]);
  let releaseFirst;
  const firstResponse = new Promise((resolve) => { releaseFirst = resolve; });
  let refreshes = 0;
  let active = 0;
  let maxActive = 0;
  let invalidCookies = 0;
  let cookie = "rotation-0";
  await context.route("**/api/v1/auth/refresh", async (route) => {
    refreshes++;
    active++;
    maxActive = Math.max(maxActive, active);
    const received = (await route.request().allHeaders()).cookie || "";
    if (!received.includes(`refresh_token=${cookie}`)) {
      invalidCookies++;
      active--;
      return route.fulfill({ status: 401, json: { detail: "Expired cookie" } });
    }
    cookie = `rotation-${refreshes}`;
    if (refreshes === 1) await firstResponse;
    await route.fulfill({
      json: { access_token: `access-${refreshes}` },
      headers: { "set-cookie": `refresh_token=${cookie}; Path=/api/v1/auth; HttpOnly; SameSite=Lax` },
    });
    active--;
  });
  await context.route("**/api/v1/users/me", (route) => {
    expect(route.request().headers().authorization).toMatch(/^Bearer access-[12]$/);
    return route.fulfill({ json: user });
  });
  await context.route("**/api/v1/notifications", (route) => route.fulfill({ json: [] }));
  const second = await context.newPage();
  try {
    await page.goto(live);
    await expect.poll(() => refreshes).toBe(1);
    await second.goto(live);
    // Prove the second tab is actually waiting on the browser's shared lock.
    await expect.poll(() => second.evaluate(async () => {
      const state = await navigator.locks.query();
      return state.pending.filter((lock) => lock.name === "cs160-auth-cookie").length;
    })).toBe(1);
    expect(refreshes).toBe(1);
    releaseFirst();
    await expect(page.getByText("Margaret", { exact: true })).toBeVisible();
    await expect(second.getByText("Margaret", { exact: true })).toBeVisible();
    expect(refreshes).toBe(2); // one per tab, not one per StrictMode effect
    expect(maxActive).toBe(1);
    expect(invalidCookies).toBe(0);
    for (const tab of [page, second]) {
      expect(await tab.evaluate(() => ({
        local: Object.keys(localStorage), session: Object.keys(sessionStorage),
        cookies: document.cookie,
      }))).toEqual({ local: [], session: [], cookies: "" });
    }
  } finally {
    releaseFirst();
    await second.close();
  }
});

test("logout waits for another tab's rotation and uses the new cookie", async ({ context, page }) => {
  // Run the real adapter in two pages, with real browser locks and a shared cookie jar.
  await context.addCookies([{
    name: "refresh_token", value: "old", domain: "127.0.0.1",
    path: "/api/v1/auth", httpOnly: true, sameSite: "Lax",
  }]);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let refreshStarted = false;
  let loggedOut = false;
  await context.route("**/api/v1/auth/refresh", async (route) => {
    refreshStarted = true;
    await gate;
    return route.fulfill({
      json: { access_token: "new" },
      headers: { "set-cookie": "refresh_token=new; Path=/api/v1/auth; HttpOnly; SameSite=Lax" },
    });
  });
  await context.route("**/api/v1/auth/logout", async (route) => {
    expect((await route.request().allHeaders()).cookie).toContain("refresh_token=new");
    loggedOut = true;
    return route.fulfill({
      status: 204,
      headers: { "set-cookie": "refresh_token=; Path=/api/v1/auth; HttpOnly; Max-Age=0" },
    });
  });
  await context.route("**/api/v1/users/me", (route) => route.fulfill({ json: user }));
  // A blank same-origin page avoids starting the App's own restore effect.
  await context.route("**/auth-test", (route) => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Auth test</title>" }));
  const second = await context.newPage();
  try {
    await Promise.all([page.goto(`${live}/auth-test`), second.goto(`${live}/auth-test`)]);
    await page.evaluate(async () => {
      const { createApi } = await import("/src/models/api.js");
      window.restoring = createApi().restoreSession();
    });
    await expect.poll(() => refreshStarted).toBe(true);
    await second.evaluate(async () => {
      const { createApi } = await import("/src/models/api.js");
      window.signingOut = createApi().signOut();
    });
    await expect.poll(() => second.evaluate(async () => (await navigator.locks.query()).pending.length)).toBe(1);
    expect(loggedOut).toBe(false);
    release();
    await Promise.all([
      page.evaluate(() => window.restoring), second.evaluate(() => window.signingOut),
    ]);
    expect(loggedOut).toBe(true);
    expect((await context.cookies()).filter((cookie) => cookie.name === "refresh_token")).toHaveLength(0);
  } finally {
    release();
    await second.close();
  }
});

test("unsupported session coordination reports an error without racing refresh requests", async ({ page }) => {
  let refreshes = 0;
  await page.addInitScript(() => Object.defineProperty(navigator, "locks", { value: undefined }));
  await page.route("**/api/v1/auth/refresh", (route) => {
    refreshes++;
    return route.fulfill({ json: { access_token: "unused" } });
  });
  await page.goto(live);
  await expect(page.getByRole("alert")).toContainText("Secure sign-in is unavailable");
  expect(refreshes).toBe(0);
});
