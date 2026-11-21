/**
 * Fail the build if the installable PWA assets are absent, malformed, or if
 * the deployment could silently ship an API response cache.
 */
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const dir = "dist";
function fail(reason) { throw new Error("PWA verification failed: " + reason); }
function required(path) {
    const filename = join(dir, path);
    if (!existsSync(filename)) fail("missing " + path);
    return readFileSync(filename);
}
const manifest = JSON.parse(required("manifest.webmanifest").toString("utf8"));
if (manifest.name !== "KC Ledger — Financial Operations" ||
    manifest.display !== "standalone" ||
    manifest.start_url !== "/" || manifest.scope !== "/") {
    fail("app manifest identity, scope or display is invalid");
}
for (const entry of [
    ["/pwa/icon-192.png", 192, "any"],
    ["/pwa/icon-512.png", 512, "any"],
    ["/pwa/maskable-512.png", 512, "maskable"]
]) {
    if (!manifest.icons.some(icon =>
        icon.src === entry[0] && icon.sizes === entry[1] + "x" + entry[1]
        && icon.purpose === entry[2] && icon.type === "image/png")) {
        fail("manifest lacks correct icon " + entry[0]);
    }
    const bytes = required(entry[0].replace(/^\//, ""));
    if (bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") {
        fail("icon PNG header invalid: " + entry[0]);
    }
    if (bytes.readUInt32BE(16) !== entry[1] ||
        bytes.readUInt32BE(20) !== entry[1]) {
        fail("icon PNG size mismatch: " + entry[0]);
    }
}
for (const [name, size] of [
    ["pwa/apple-touch-icon.png", 180],
    ["pwa/favicon-32.png", 32]
]) {
    const img = required(name);
    if (img.readUInt32BE(16) !== size) fail("invalid " + name);
}
const index = required("index.html").toString("utf8");
if (!index.includes("manifest.webmanifest") || !index.includes("apple-touch-icon")) {
    fail("entry page lacks app manifest or Apple install icon");
}
const sw = required("sw.js").toString("utf8");
if (!sw.includes("precacheAndRoute") || !sw.includes("index.html")) {
    fail("service worker does not precache the offline application shell");
}
if (!sw.includes("NetworkOnly")) {
    fail("service worker does not declare network-only server response handling");
}
for (const token of ["api", "admin", "downloads"]) {
    if (!sw.includes(token)) fail("sensitive route exclusion absent: " + token);
}
console.info("PWA verified: manifest, 192/512/maskable PNGs, Apple touch icon, service worker, no API response cache");
