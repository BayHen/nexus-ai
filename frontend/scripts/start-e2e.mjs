import { cpSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const standalone = resolve(".next/standalone");
const staticSource = resolve(".next/static");
const staticTarget = resolve(standalone, ".next/static");
if (existsSync(staticSource)) {
  mkdirSync(staticTarget, { recursive: true });
  cpSync(staticSource, staticTarget, { recursive: true });
}
const publicSource = resolve("public");
if (existsSync(publicSource)) cpSync(publicSource, resolve(standalone, "public"), { recursive: true });
process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = "3100";
await import(pathToFileURL(resolve(standalone, "server.js")).href);
