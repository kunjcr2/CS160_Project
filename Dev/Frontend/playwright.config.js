import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 30000,
  workers: 2,
  use: {
    channel: process.env.PW_CHANNEL || "msedge",
    headless: true,
    timezoneId: "America/Los_Angeles",
    screenshot: "only-on-failure",
  },
});
