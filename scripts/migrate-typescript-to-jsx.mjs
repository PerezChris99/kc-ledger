#!/usr/bin/env node
/**
 * One-time whole-repository TS/TSX -> JS/JSX migration.
 * Uses the TypeScript compiler for syntax-aware type erasure (never regex for TS).
 * All source/config/test changes are committed together after lint and build pass.
 */
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const root = process.cwd();
const migrated = [];
function absolute(file) { return path.join(root, file); }
function update(file, transform) {
  const p = absolute(file);
  const before = fs.readFileSync(p, "utf8");
  const after = transform(before);
  if (after === before) throw new Error("Migration replacement missed its anchor in " + file);
  fs.writeFileSync(p, after, "utf8");
}
function allTypescript(dir) {
  const found = [];
  for (const ent of fs.readdirSync(absolute(dir), { withFileTypes: true })) {
    const file = path.posix.join(dir, ent.name);
    if (ent.isDirectory()) found.push(...allTypescript(file));
    else if (/\.tsx?$/.test(file) && !/\.d\.ts$/.test(file)) found.push(file);
  }
  return found;
}
const files = [
  ...allTypescript("frontend"),
  ...allTypescript("e2e"),
  "vite.config.ts",
  "playwright.config.ts",
];
if (!files.includes("frontend/src/App.tsx") || !files.includes("frontend/main.tsx")) {
  throw new Error("Expected React TypeScript entrypoints are missing.");
}
for (const file of files) {
  const src = fs.readFileSync(absolute(file), "utf8");
  const dest = file.replace(/\.tsx$/, ".jsx").replace(/\.ts$/, ".js");
  if (fs.existsSync(absolute(dest))) throw new Error("Refusing to overwrite " + dest);
  const result = ts.transpileModule(src, {
    fileName: file,
    reportDiagnostics: true,
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
      jsx: ts.JsxEmit.Preserve,
      isolatedModules: true,
      removeComments: false,
    },
  });
  const errors = (result.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) {
    throw new Error("Failed type erasure in " + file + ": " +
      errors.map(d => ts.flattenDiagnosticMessageText(d.messageText, "\n")).join("\n"));
  }
  fs.writeFileSync(absolute(dest), result.outputText, "utf8");
  fs.unlinkSync(absolute(file));
  migrated.push({ from: file, to: dest });
}
for (const config of ["tsconfig.json", "tsconfig.app.json", "tsconfig.node.json"]) {
  if (fs.existsSync(absolute(config))) fs.unlinkSync(absolute(config));
}
update("index.html", s => s.replace("/frontend/main.tsx", "/frontend/main.jsx"));
update("frontend.Dockerfile", s => s
  .replace("COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./",
           "COPY index.html vite.config.js ./"));
update("desktop/build_windows.ps1", s => s
  .replace("npm run typecheck", "npm run lint")
  .replace("Frontend type checking failed", "Frontend lint failed"));
update(".github/workflows/ci.yml", s => s
  .replace("Lint, typecheck, bundle", "Lint and production bundle")
  .replace("          npm run typecheck\n", ""));
update("README.md", s => s
  .replaceAll("TypeScript", "JavaScript (JSX)")
  .replaceAll("npm run typecheck\n", ""));
const pkgPath = absolute("package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
pkg.scripts.build = "vite build";
delete pkg.scripts.typecheck;
pkg.scripts.lint = "eslint frontend e2e vite.config.js playwright.config.js --max-warnings=0";
for (const name of ["typescript", "@types/react", "@types/react-dom",
                    "@typescript-eslint/eslint-plugin", "@typescript-eslint/parser"]) {
  delete pkg.devDependencies[name];
}
pkg.devDependencies["eslint-plugin-react"] = "^7.37.5";
pkg.devDependencies.globals = "^16.4.0";
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
const lintConfig = [
  'import react from "eslint-plugin-react";',
  'import globals from "globals";',
  "",
  "export default [{",
  '  files: ["frontend/**/*.{js,jsx}", "e2e/**/*.js", "vite.config.js", "playwright.config.js"],',
  "  languageOptions: {",
  '    ecmaVersion: "latest",',
  '    sourceType: "module",',
  "    globals: { ...globals.browser, ...globals.node },",
  "    parserOptions: { ecmaFeatures: { jsx: true } },",
  "  },",
  "  plugins: { react },",
  '  settings: { react: { version: "detect" } },',
  "  rules: {",
  '    "react/jsx-uses-vars": "error",',
  '    "react/jsx-uses-react": "error",',
  '    "no-unused-vars": ["error", {',
  '      argsIgnorePattern: "^_",',
  '      varsIgnorePattern: "^_",',
  '      caughtErrors: "none",',
  '      ignoreRestSiblings: true,',
  "    }],",
  "  },",
  "}];",
  "",
].join("\n");
fs.writeFileSync(absolute("eslint.config.js"), lintConfig, "utf8");
fs.unlinkSync(absolute("scripts/migrate-typescript-to-jsx.mjs"));
fs.unlinkSync(absolute(".github/workflows/javascript-migration.yml"));
if (migrated.length < 12) throw new Error("Unexpectedly small TypeScript migration: " + migrated.length);
console.log("Converted " + migrated.length + " source/config/test files to JS/JSX:");
for (const item of migrated) console.log("  " + item.from + " -> " + item.to);
console.log("Removed obsolete tsconfig files, TypeScript compiler, parser and type packages.");
console.log("Updated React/Vite, lint, Docker, Playwright, README and installer build wiring.");
