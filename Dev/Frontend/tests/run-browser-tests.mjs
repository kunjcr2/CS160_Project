import { spawn } from "node:child_process";
import { once } from "node:events";
import { resolve } from "node:path";

const servers = [];
let runner;

// Spawn Node directly so Windows cleanup does not depend on npm/cmd process trees.
function startServer(port, mode) {
  return new Promise((done, reject) => {
    const child = spawn(process.execPath, ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
      windowsHide: true,
      env: { ...process.env, VITE_DATA_MODE: mode, VITE_NOTIFICATION_STREAM_PATH: "", VITE_NOTIFICATIONS_PATH: "/notifications", NO_COLOR: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    servers.push(child);
    let output = "";
    const timeout = setTimeout(() => reject(new Error(`Vite on ${port} did not start. ${output}`)), 20000);
    child.on("error", (error) => { clearTimeout(timeout); reject(error); });
    child.once("exit", (code) => { clearTimeout(timeout); reject(new Error(`Vite exited (${code}). ${output}`)); });
    child.stderr.on("data", (data) => { output += data; });
    child.stdout.on("data", (data) => {
      output += data;
      if (output.includes(`http://127.0.0.1:${port}`)) { clearTimeout(timeout); done(); }
    });
  });
}

async function stop(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  const exited = once(child, "exit");
  child.kill();
  await exited;
}

process.on("SIGINT", () => { runner?.kill(); servers.forEach((child) => child.kill()); });
process.on("SIGTERM", () => { runner?.kill(); servers.forEach((child) => child.kill()); });

try {
  await Promise.all([startServer(5180, "demo"), startServer(5181, "live")]);
  runner = spawn(process.execPath, ["node_modules/@playwright/test/cli.js", "test", ...process.argv.slice(2)], {
    windowsHide: true,
    stdio: "inherit",
    env: { ...process.env, PWTEST_CACHE_DIR: process.env.PWTEST_CACHE_DIR || resolve(".npm-cache/playwright-transform") },
  });
  const [code] = await once(runner, "exit");
  process.exitCode = code ?? 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await Promise.all(servers.map(stop));
}
