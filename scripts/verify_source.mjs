// Protect the completed TS-to-JSX migration and avoid stale language claims.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.cwd();
const exclude = new Set([
  ".git", "node_modules", "dist", "build", "installer-output",
  "playwright-report", "test-results", ".venv", "__pycache__",
]);
const offending = [];
function visit(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!exclude.has(entry.name)) visit(join(directory, entry.name));
    } else if (entry.isFile()) {
      const path = join(directory, entry.name);
      const name = relative(root, path).replaceAll("\\", "/");
      if (/\.(?:ts|tsx|mts|cts)$/i.test(entry.name) ||
          /^tsconfig(?:\..*)?\.json$/i.test(entry.name)) {
        offending.push(name);
      }
    }
  }
}
visit(root);
for (const required of [
  "frontend/main.jsx", "frontend/src/App.jsx",
  "vite.config.js", "playwright.config.js",
  "e2e/financial-workflows.spec.js",
]) {
  if (!existsSync(join(root, required))) offending.push("Missing " + required);
}
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
for (const key of ["dependencies", "devDependencies"]) {
  for (const dependency of Object.keys(pkg[key] ?? {})) {
    if (dependency === "typescript" || dependency.startsWith("@typescript-eslint/")) {
      offending.push("Stale " + key + ": " + dependency);
    }
  }
}
if (offending.length) {
  console.error("JavaScript/JSX source verification failed:\n" + offending.join("\n"));
  process.exitCode = 1;
} else {
  console.log("Verified: JSX/JS source, JavaScript tooling, no TypeScript or tsconfig files.");
}
