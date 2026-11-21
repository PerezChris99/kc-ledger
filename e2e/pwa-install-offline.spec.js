import { test, expect } from "@playwright/test";

test("PWA manifest contains true PNG and maskable installation assets", async ({ request }) => {
    const manifestRequest = await request.get("/manifest.webmanifest");
    expect(manifestRequest.ok()).toBeTruthy();
    const manifest = await manifestRequest.json();
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/");
    expect(manifest.scope).toBe("/");
    expect(manifest.icons).toEqual(expect.arrayContaining([
        expect.objectContaining({
            src: "/pwa/icon-192.png", sizes: "192x192", purpose: "any"
        }),
        expect.objectContaining({
            src: "/pwa/icon-512.png", sizes: "512x512", purpose: "any"
        }),
        expect.objectContaining({
            src: "/pwa/maskable-512.png", sizes: "512x512", purpose: "maskable"
        })
    ]));
    for (const [name, dimension] of [
        ["/pwa/icon-192.png", 192],
        ["/pwa/icon-512.png", 512],
        ["/pwa/maskable-512.png", 512],
        ["/pwa/apple-touch-icon.png", 180]
    ]) {
        const result = await request.get(name);
        expect(result.ok()).toBeTruthy();
        const bytes = await result.body();
        expect(bytes.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
        expect(bytes.readUInt32BE(16)).toBe(dimension);
        expect(bytes.readUInt32BE(20)).toBe(dimension);
    }
});

test("installed app shell loads offline without storing private ledger API responses", async ({ page, context }) => {
    await page.goto("/");
    await expect(page.getByLabel("USERNAME")).toBeVisible();
    await page.evaluate(async () => {
        if (!("serviceWorker" in navigator)) throw new Error("Service worker unsupported");
        await navigator.serviceWorker.ready;
    });
    await page.reload();
    await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
    const assets = await page.evaluate(async () => {
        const out = [];
        for (const cacheName of await caches.keys()) {
            const c = await caches.open(cacheName);
            for (const key of await c.keys()) out.push(new URL(key.url).pathname);
        }
        return out;
    });
    expect(assets).toContain("/index.html");
    expect(assets.some(key => /^\/(api|admin|downloads)(\/|$)/.test(key))).toBe(false);
    await context.setOffline(true);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("OFFLINE MODE")).toBeVisible();
    await expect(page.getByText(/No financial data is being cached/)).toBeVisible();
    await expect(page.locator("main").getByText(/live server/)).toBeVisible();
    await context.setOffline(false);
    await page.reload();
    await expect(page.getByLabel("USERNAME")).toBeVisible();
});

test("local installed PWA can reach loopback backend when the OS reports no internet", async ({ page, context }) => {
    await context.addInitScript(() => {
        Object.defineProperty(Navigator.prototype, "onLine", {
            configurable: true, get: () => false
        });
    });
    await page.goto("/");
    const health = await page.evaluate(async () => {
        const response = await fetch("/api/health", { cache: "no-store" });
        return response.ok;
    });
    expect(health).toBe(true);
    await expect(page.getByLabel("USERNAME")).toBeVisible();
    await expect(page.getByText("OFFLINE MODE")).toHaveCount(0);
});

test("authenticated API records stay out of service worker caches, and logout clears in-memory financial queries", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("USERNAME").fill("ledger-ci-owner");
    await page.getByLabel("PASSWORD").fill("CI-only-Password-123456789-strong");
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    await page.getByRole("navigation", { name: "Main navigation" })
        .getByRole("button", { name: "Intelligence", exact: true }).click();
    await expect(page.getByRole("tab", { name: "Business command" })).toBeVisible();
    const privatePaths = await page.evaluate(async () => {
        const keys = await caches.keys();
        const urls = [];
        for (const name of keys) {
            const cache = await caches.open(name);
            for (const request of await cache.keys()) {
                urls.push(new URL(request.url).pathname);
            }
        }
        return urls.filter(path => /^\/(api|admin|downloads)(\/|$)/.test(path));
    });
    expect(privatePaths).toEqual([]);
    await page.getByRole("button", { name: "Sign out" }).first().click();
    await expect(page.getByLabel("USERNAME")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toHaveCount(0);
});
