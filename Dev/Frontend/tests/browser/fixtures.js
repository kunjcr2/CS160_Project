import { readFile } from "node:fs/promises";
import { resolve, sep, extname } from "node:path";
import { test as base, expect } from "@playwright/test";

// Optional offline mode serves local build artifacts through Playwright routing.
// It exercises the real browser UI/locks/cookies without opening HTTP sockets.
export const test = base.extend({
  context: async ({ context }, use) => {
    if (process.env.PW_OFFLINE_BUILD === "1") {
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.hostname !== "127.0.0.1") return route.abort();
        if (url.pathname.startsWith("/api/"))
          return route.fulfill({ status: 503, json: { detail: "No API mock registered." } });
        const sourceModule = url.pathname.startsWith("/src/models/");
        const root = sourceModule
          ? resolve("src/models")
          : resolve(`.npm-cache/offline-${url.port === "5180" ? "demo" : "live"}`);
        const relative = sourceModule
          ? url.pathname.slice("/src/models/".length)
          : url.pathname === "/" ? "index.html" : url.pathname.slice(1);
        const file = resolve(root, decodeURIComponent(relative));
        if (!file.startsWith(root + sep)) return route.abort();
        try {
          const contentType = {
            ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
            ".svg": "image/svg+xml", ".png": "image/png",
          }[extname(file)] || "application/octet-stream";
          return route.fulfill({ body: await readFile(file), contentType });
        } catch {
          return route.fulfill({ status: 404, body: "Local test asset not found" });
        }
      });
    }
    await use(context);
  },
});

export { expect };
