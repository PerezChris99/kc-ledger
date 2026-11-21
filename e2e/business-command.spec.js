import { test, expect } from "@playwright/test";

async function signIn(page) {
    await page.goto("/");
    await page.getByLabel("USERNAME").fill("ledger-ci-owner");
    await page.getByLabel("PASSWORD").fill("CI-only-Password-123456789-strong");
    await page.getByRole("button", { name: /Open console/i }).click();
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

test("business command analyzes cash, goals, previous strategies and client pitches", async ({ page }) => {
    await signIn(page);
    const navigation = page.getByRole("navigation", { name: "Main navigation" });
    const clientName = "Business strategy prospect " + Date.now().toString(36);

    await navigation.getByRole("button", { name: "Clients", exact: true }).click();
    await page.getByRole("button", { name: "Add client" }).click();
    const clientDialog = page.getByRole("dialog", { name: "NEW CLIENT RECORD" });
    await clientDialog.getByLabel("CLIENT NAME").fill(clientName);
    await clientDialog.getByRole("button", { name: "Create client" }).click();
    await expect(clientDialog).toBeHidden();

    await navigation.getByRole("button", { name: "Intelligence", exact: true }).click();
    await expect(page.getByRole("tab", { name: "Business command" })).toHaveAttribute(
        "aria-selected", "true"
    );
    await expect(page.getByText("NET CASH RESULT")).toBeVisible();
    await expect(page.getByText("not audited profit or loss")).toBeVisible();
    await expect(page.getByText("RECEIPTS VS COSTS")).toBeVisible();
    await expect(page.getByText("WHERE THE COSTS GO")).toBeVisible();

    await page.getByRole("tab", { name: "Strategy & goals" }).click();
    const uniqueGoal = "E2E recorded strategy goal " + Date.now().toString(36);
    await page.getByLabel("OBJECTIVE NAME").fill(uniqueGoal);
    await page.getByLabel("MEASURABLE OUTCOME").selectOption("active_clients");
    await page.getByLabel("TARGET VALUE").fill("10");
    await page.getByRole("button", { name: "Save business goal" }).click();
    await expect(page.getByText(uniqueGoal).first()).toBeVisible();
    await expect(page.getByText("Objective recorded.", { exact: false })).toBeVisible();

    await page.getByLabel("STRATEGY / ACTION").fill("E2E conduct discovery calls");
    await page.getByLabel("TYPE").selectOption("outreach");
    await page.getByLabel("LINK TO GOAL").selectOption({
        label: uniqueGoal
    });
    await page.getByLabel("EXPECTED CHANGE").fill("At least 10 active clients");
    await page.getByRole("button", { name: "Log strategy and baseline" }).click();
    await expect(page.getByText("E2E conduct discovery calls").first()).toBeVisible();
    await expect(page.getByText("Strategy logged with a baseline", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Review / close experiment" }).first().click();
    await page.getByLabel("OUTCOME AND WHAT YOU LEARNED").fill("Run another cycle before deciding.");
    await page.getByRole("button", { name: "Save review" }).click();
    await expect(page.getByText("Your strategy review is saved", { exact: false })).toBeVisible();

    await page.getByRole("tab", { name: "Client approach" }).click();
    await page.getByLabel("SELECT CLIENT").selectOption({
        label: clientName
    });
    await expect(page.getByText("Recommended approach")).toBeVisible();
    await expect(page.getByText("Proposal outline")).toBeVisible();

    await page.getByRole("tab", { name: "Advisor & challenge" }).click();
    await expect(page.getByText("DECISION CHALLENGES AND WARNINGS")).toBeVisible();
    await page.getByRole("button", { name: "Challenge my strategy" }).click();
    await expect(page.getByText("Local business advisor")).toBeVisible();
    await page.screenshot({ path: "test-results/business-command.png", fullPage: true });
});
