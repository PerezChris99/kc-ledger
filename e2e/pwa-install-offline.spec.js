import { createServer } from "node:http";
import { once } from "node:events";
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
    await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
    await page.reload();
    await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
    const privateResponse = await page.evaluate(async () => {
        const response = await fetch("/api/clients", { cache: "no-store" });
        return { status: response.status, cacheControl: response.headers.get("Cache-Control") };
    });
    expect(privateResponse.status).toBe(200);
    expect(privateResponse.cacheControl).toContain("no-store");
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


test("sign-out in one installed browser tab closes private views in other tabs", async ({ page, context }) => {
    await page.goto("/");
    await page.getByLabel("USERNAME").fill("ledger-ci-owner");
    await page.getByLabel("PASSWORD").fill("CI-only-Password-123456789-strong");
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();

    const otherTab = await context.newPage();
    await otherTab.goto("/");
    await expect(otherTab.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    await page.getByRole("button", { name: "Sign out" }).first().click();
    await expect(page.getByLabel("USERNAME")).toBeVisible();
    await expect(otherTab.getByLabel("USERNAME")).toBeVisible();
    await expect(otherTab.getByRole("navigation", { name: "Main navigation" })).toHaveCount(0);
});

test.describe("session revalidation", () => {
    // Intercept the session response to keep the verification window open
    // deterministically. The adjacent cache tests exercise the real worker.
    test.use({ serviceWorkers: "block" });

    test("reconnect hides old financial views until the server verifies the session", async ({ page, context }) => {
        await page.goto("/");
        await page.getByLabel("USERNAME").fill("ledger-ci-owner");
        await page.getByLabel("PASSWORD").fill("CI-only-Password-123456789-strong");
        await page.getByRole("button", { name: /Open console/i }).click();
        const navigation = page.getByRole("navigation", { name: "Main navigation" });
        await expect(navigation).toBeVisible();

        await context.setOffline(true);
        await expect(page.getByText("OFFLINE MODE")).toBeVisible();

        let releaseSession;
        const sessionGate = new Promise(resolve => { releaseSession = resolve; });
        await page.route("**/api/session", async route => {
            await sessionGate;
            const response = await page.request.get("/api/session");
            await route.fulfill({ response });
        });
        try {
            await context.setOffline(false);
            await expect(page.getByText("VERIFYING PRIVATE SESSION")).toBeVisible();
            await expect(navigation).toHaveCount(0);
            await context.clearCookies({ name: "sessionid" });
        } finally {
            releaseSession();
        }
        await expect(page.getByLabel("USERNAME")).toBeVisible();
        await expect(navigation).toHaveCount(0);
    });
});

test("a waiting service worker can be dismissed, reopened and applied with confirmation", async ({ page, baseURL }) => {
    let workerRevision = 1;
    // A separate origin serves the built app and changes only the worker bytes.
    // Chromium performs the real install/wait/activate lifecycle.
    const server = createServer(async (req, res) => {
        try {
            const upstream = await fetch(new URL(req.url, baseURL));
            const body = req.url === "/sw.js" && upstream.ok
                ? `${await upstream.text()}\n// Test worker revision ${workerRevision}\n`
                : Buffer.from(await upstream.arrayBuffer());
            res.writeHead(upstream.status, {
                "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
                "Cache-Control": "no-store",
            }).end(body);
        } catch {
            res.writeHead(502).end();
        }
    });
    server.listen(0, "127.0.0.1");
    await once(server, "listening");
    try {
        await page.goto(`http://127.0.0.1:${server.address().port}/`);
        await expect(page.getByLabel("USERNAME")).toBeVisible();
        await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
        await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

        workerRevision++;
        await page.evaluate(async () => {
            const registration = await navigator.serviceWorker.ready;
            await registration.update();
        });
        const update = page.getByRole("button", { name: "Update now" });
        await expect(update).toBeVisible();
        await page.getByRole("button", { name: "Dismiss app update notice" }).click();
        await page.getByRole("button", { name: "Update ready" }).click();
        await expect(update).toBeVisible();

        page.once("dialog", dialog => dialog.dismiss());
        await update.click();
        expect(await page.evaluate(async () => Boolean((await navigator.serviceWorker.ready).waiting))).toBe(true);
        page.once("dialog", dialog => dialog.accept());
        await update.click();
        await expect.poll(() => page.evaluate(async () => {
            const registration = await navigator.serviceWorker.getRegistration();
            return Boolean(registration?.active && !registration.waiting && !registration.installing);
        })).toBe(true);
    } finally {
        await page.goto("about:blank").catch(() => {});
        await new Promise(resolve => server.close(resolve));
    }
});
