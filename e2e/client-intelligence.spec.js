import { test, expect } from "@playwright/test";

const username = "ledger-ci-owner";
const password = "CI-only-Password-123456789-strong";

async function login(page) {
    await page.goto("/");
    await page.getByLabel("USERNAME").fill(username);
    await page.getByLabel("PASSWORD").fill(password);
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

async function newClient(page, name) {
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("button", { name: "Clients", exact: true }).click();
    await page.getByRole("button", { name: "Add client" }).click();
    const dialog = page.getByRole("dialog", { name: "NEW CLIENT RECORD" });
    await dialog.getByLabel("CLIENT NAME").fill(name);
    await dialog.getByRole("button", { name: "Create client" }).click();
    await expect(dialog).toBeHidden();
}

async function recordSignal(page, code) {
    await page.getByLabel("OBSERVED BEHAVIOUR").selectOption(code);
    await page.getByRole("button", { name: "Record and recalculate" }).click();
    await expect(page.getByText("Documented signal added.", { exact: false })).toBeVisible();
}

test("intelligence charts, factual history matching, owner review and local advice", async ({ page }) => {
    await login(page);
    const unique = Date.now().toString(36);
    const historical = `Historical Scope and Payment ${unique}`;
    const current = `Current Scope and Payment ${unique}`;
    await newClient(page, historical);
    await newClient(page, current);

    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("button", { name: "Intelligence", exact: true }).click();
    await expect(page.getByText("CLIENT HEALTH DISTRIBUTION")).toBeVisible();
    await expect(page.getByText("HEALTH SCORE VS RISK INDEX")).toBeVisible();
    await expect(page.locator(".intel-chart canvas").first()).toBeVisible();

    await page.getByRole("tab", { name: "Client analysis" }).click();
    const selector = page.getByLabel("Select a client for intelligence analysis");
    await selector.selectOption(
        await selector.locator("option").filter({ hasText: historical }).last().getAttribute("value")
    );
    await recordSignal(page, "scope_creep");
    await recordSignal(page, "chargeback");

    await selector.selectOption(
        await selector.locator("option").filter({ hasText: current }).last().getAttribute("value")
    );
    await recordSignal(page, "scope_creep");
    await recordSignal(page, "chargeback");
    await expect(page.getByText(historical, { exact: true }).last()).toBeVisible();
    await expect(page.getByText(/Common observed behaviours:/)).toContainText("Chargeback");

    await page.getByRole("button", { name: "Generate advisory report" }).click();
    await expect(page.getByText("Local advisory", { exact: true })).toBeVisible();

    await page.getByRole("tab", { name: "Pattern watch" }).click();
    await expect(page.getByText("BEHAVIOUR HEATMAP")).toBeVisible();
    await expect(page.getByText("HISTORICAL PATTERN MATCHES")).toBeVisible();
    await page.getByRole("button", { name: "Mark reviewed" }).first().click();
    await expect(page.getByText("No unreviewed cross-client matches.", { exact: false })).toBeVisible();
    await page.screenshot({ path: "test-results/client-intelligence.png", fullPage: true });
});
