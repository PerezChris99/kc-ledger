import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
    testDir: "./e2e",
    timeout: 30_000,
    retries: process.env.CI ? 1 : 0,
    reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
    use: {
        ...devices["Desktop Chrome"],
        baseURL: process.env.LEDGER_TEST_BASE_URL ?? "http://127.0.0.1:8080",
        screenshot: "only-on-failure",
        trace: "retain-on-failure",
    },
});
