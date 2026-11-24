import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";
const username = "ledger-ci-owner";
const password = "CI-only-Password-123456789-strong";
async function signIn(page) {
    await page.goto("/");
    await page.getByLabel("USERNAME").fill(username);
    await page.getByLabel("PASSWORD").fill(password);
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}
test("owner can log in, navigate each financial page, and sign out", async ({ page }) => {
    await signIn(page);
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    for (const name of [
        "Dashboard", "Clients", "Invoices", "Instalment plans",
        "Insights", "Avoid", "History",
    ]) {
        await nav.getByRole("button", { name, exact: true }).click();
        await expect(page.getByRole("heading", { name, exact: true }).first()).toBeVisible();
        await page.screenshot({ path: "test-results/" + name.toLowerCase().replaceAll(" ", "-") + ".png", fullPage: true });
    }
    await page.getByRole("button", { name: "Settings", exact: true }).last().click();
    await expect(page.getByText("BUSINESS TARGETS")).toBeVisible();
    await page.screenshot({ path: "test-results/settings.png", fullPage: true });
    await page.getByRole("button", { name: "Sign out", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: "Sign in to your ledger" })).toBeVisible();
});
test("owner creates a client, invoices the client, and records a partial payment", async ({ page }) => {
    const suffix = randomUUID().slice(0, 8);
    const customer = `E2E Customer ${suffix}`;
    const invoice = `E2E-${suffix}`;
    await signIn(page);
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("button", { name: "Clients" }).click();
    await page.getByRole("button", { name: "Add client" }).click();
    const clientDialog = page.getByRole("dialog", { name: "NEW CLIENT RECORD" });
    await clientDialog.getByLabel("CLIENT NAME").fill(customer);
    await clientDialog.getByLabel("COMPANY").fill("E2E Verified Business");
    await clientDialog.getByRole("button", { name: "Create client" }).click();
    await expect(clientDialog).toBeHidden();
    await expect(page.getByText(customer).first()).toBeVisible();
    await nav.getByRole("button", { name: "Invoices" }).click();
    await page.getByRole("button", { name: "Create invoice" }).click();
    const invoiceDialog = page.getByRole("dialog", { name: "CREATE INVOICE" });
    await invoiceDialog.getByLabel("CLIENT", { exact: true }).selectOption({ label: `${customer} · E2E Verified Business` });
    await invoiceDialog.getByLabel("INVOICE NUMBER").fill(invoice);
    await invoiceDialog.getByLabel("TITLE").fill("Application design services");
    await invoiceDialog.getByLabel("AMOUNT").fill("100.00");
    await invoiceDialog.getByRole("button", { name: "Create invoice" }).click();
    await expect(invoiceDialog).toBeHidden();
    await expect(page.getByText(invoice).first()).toBeVisible();
    const invoiceRow = page.getByRole("row").filter({ hasText: invoice });
    await invoiceRow.getByRole("button", { name: "Record payment" }).click();
    const paymentDialog = page.getByRole("dialog", { name: /RECORD PAYMENT/ });
    await paymentDialog.getByLabel(/PAYMENT AMOUNT/).fill("25.00");
    await paymentDialog.getByRole("button", { name: "Save payment" }).click();
    await expect(paymentDialog).toBeHidden();
    await expect(invoiceRow).toContainText("75.00");
    await nav.getByRole("button", { name: "Clients" }).click();
    await page.getByRole("row").filter({ hasText: customer }).first().click();
    page.once("dialog", dialog => dialog.accept("Receipt was assigned to the wrong invoice"));
    await page.getByRole("button", { name: "Reverse payment" }).click();
    await expect(page.getByRole("button", { name: "Reverse payment" })).toHaveCount(0);
    await nav.getByRole("button", { name: "Invoices" }).click();
    await invoiceRow.getByRole("button", { name: "Record payment" }).click();
    await expect(paymentDialog.getByLabel(/PAYMENT AMOUNT/)).toHaveValue("100.00");
    await paymentDialog.getByRole("button", { name: "Save payment" }).click();
    await expect(paymentDialog).toBeHidden();
    await expect(invoiceRow.getByText("paid", { exact: true })).toBeVisible();
});

test("owner can enter the private workspace on a phone-sized screen", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByLabel("USERNAME").fill(username);
    await page.getByLabel("PASSWORD").fill(password);
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true }).first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
