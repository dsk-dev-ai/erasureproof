import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const apiOnly = process.argv.includes("--api-only");
const webOnly = process.argv.includes("--web-only");

if (apiOnly && webOnly) {
  console.error("Choose either --api-only or --web-only, not both.");
  process.exit(2);
}

function cliCommand() {
  if (process.env.ERASUREPROOF_CLI) return process.env.ERASUREPROOF_CLI;
  const candidates = [
    join(root, ".venv", "bin", "erasureproof"),
    join(root, ".venv", "Scripts", "erasureproof.exe"),
    join(root, ".venv", "Scripts", "erasureproof"),
  ];
  return candidates.find(existsSync);
}

function start(name, command, args, cwd = root) {
  const child = spawn(command, args, { cwd, stdio: "inherit" });
  child.on("error", (error) => {
    console.error(`${name} failed to start: ${error.message}`);
  });
  return child;
}

const children = [];

if (!webOnly) {
  const cli = cliCommand();
  if (!cli) {
    console.error("ErasureProof CLI not found. Create .venv and install the project first:");
    console.error("  python3 -m venv .venv");
    console.error("  .venv/bin/pip install -e '.[dev]'");
    process.exit(1);
  }
  children.push(start("API", cli, ["serve", "--reload"]));
}

if (!apiOnly) {
  if (!existsSync(join(root, "web", "node_modules"))) {
    console.error("Console dependencies are missing. Run:");
    console.error("  npm install --prefix web");
    process.exit(1);
  }
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  children.push(start("console", npm, ["--prefix", "web", "run", "dev"]));
}

let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => {
    for (const child of children) {
      if (!child.killed) child.kill("SIGKILL");
    }
    process.exit(code);
  }, 1500).unref();
}

for (const child of children) {
  child.on("exit", (code, signal) => {
    if (!stopping) {
      console.error(`A dev process exited (${signal ?? code}); stopping the rest.`);
      stop(code ?? 1);
    }
  });
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));
