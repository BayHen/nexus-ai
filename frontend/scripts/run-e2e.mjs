import { spawn } from "node:child_process";

const server = spawn(process.execPath, ["scripts/start-e2e.mjs"], { stdio: "inherit" });
async function ready() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try { if ((await fetch("http://127.0.0.1:3100/assistant")).ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("E2E server did not become ready.");
}

let exitCode = 1;
try {
  await ready();
  const command = process.platform === "win32" ? "npx.cmd" : "npx";
  const tests = spawn(command, ["playwright", "test"], { stdio: "inherit", env: { ...process.env, PW_EXTERNAL_SERVER: "1" } });
  exitCode = await new Promise((resolve) => tests.once("exit", (code) => resolve(code ?? 1)));
} finally {
  server.kill("SIGTERM");
}
process.exit(exitCode);
