import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const version = readFileSync(resolve(root, "VERSION"), "utf8").trim();
if (!/^\d+\.\d+\.\d+$/.test(version)) throw new Error("VERSION must be MAJOR.MINOR.PATCH");
const channel = process.env.LEDGER_RELEASE_CHANNEL || "stable";
if (!["stable", "beta"].includes(channel)) throw new Error("Invalid update channel");
const minimum = process.env.LEDGER_MIN_SUPPORTED_VERSION || version;
if (!/^\d+\.\d+\.\d+$/.test(minimum)) throw new Error("Invalid minimum supported version");
let sha = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA || "unknown";
if (sha === "unknown") {
  try { sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim(); }
  catch { /* Source archive with no .git metadata */ }
}
sha = sha === "unknown" ? sha : sha.slice(0, 12);
const metadata = {
  version,
  git_sha: sha,
  build_time: process.env.LEDGER_BUILD_TIME || new Date().toISOString(),
  channel,
  min_supported_version: minimum
};
mkdirSync(resolve(root, "backend/config"), { recursive: true });
mkdirSync(resolve(root, "public"), { recursive: true });
writeFileSync(resolve(root, "backend/config/build_info.json"), JSON.stringify(metadata, null, 2) + "\n");
writeFileSync(resolve(root, "public/build-info.json"), JSON.stringify(metadata, null, 2) + "\n");
console.log("KC Ledger metadata:", metadata.version, metadata.git_sha, metadata.channel);
