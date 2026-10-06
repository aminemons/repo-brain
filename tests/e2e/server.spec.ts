import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000";
const ownerToken = process.env.OWNER_TOKEN;
const runId = process.env.E2E_RUN_ID;
const storageDir = process.env.E2E_STORAGE_DIR ?? "/app/storage";

test.describe.configure({ mode: "serial" });

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status === testInfo.expectedStatus) return;
  const screenshot = testInfo.outputPath("e2e-failure.png");
  const pageText = testInfo.outputPath("e2e-failure-dom.txt");
  await page.screenshot({ path: screenshot, fullPage: true });
  await writeFile(pageText, await page.locator("body").innerText());
  await testInfo.attach("e2e-failure.png", { path: screenshot, contentType: "image/png" });
  await testInfo.attach("e2e-failure-dom.txt", { path: pageText, contentType: "text/plain" });
});

test("owner setup, repository bots, isolated history, Najm rendering, and reviewed docs change", async ({ page }, testInfo) => {
  test.setTimeout(600_000);
  expect(ownerToken, "CI must inject the owner token without printing it").toBeTruthy();
  expect(runId, "CI must inject the same unique E2E_RUN_ID into the app and test runner").toMatch(/^[A-Za-z0-9_-]{1,80}$/);

  await page.goto(`${baseURL}/bots`);
  await expect(page.locator(".brain-auth-alert")).toContainText("valid token");
  await page.getByRole("link", { name: "Open Settings" }).click();

  const tokenField = page.getByLabel("Access token");
  await tokenField.fill("wrong-owner-token");
  await page.getByRole("button", { name: "Save token" }).click();
  await expect(page.locator(".app-token-status")).toContainText("Access token rejected. Check it and retry.", { timeout: 15_000 });
  await expect(page.locator(".brain-auth-alert")).toContainText("valid token");

  await tokenField.fill(ownerToken!);
  await page.getByRole("button", { name: "Save token" }).click();
  await expect(page.locator(".app-token-status")).toContainText("Access token accepted", { timeout: 15_000 });
  await expect(page.getByText("Service available")).toBeVisible();

  const repoOne = `${storageDir}/e2e-fixtures/${runId}/repo-one`;
  await page.getByRole("link", { name: "Bots" }).click();
  await createBot(page, repoOne, "repo-one", "E2E Repo One", "e2e-browser-model");
  await expect(page.getByRole("heading", { name: "E2E Repo One", level: 1 })).toBeVisible({ timeout: 180_000 });
  const firstBotUrl = page.url();

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("E2E Repo One Updated");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.locator(".bot-settings-form")).toContainText("Bot settings saved.");
  await expect(page.getByRole("heading", { name: "E2E Repo One Updated", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByText("Start a conversation")).toBeVisible();
  const apiKeyField = page.getByLabel("Your OpenAI API key");
  await apiKeyField.fill("e2e-only-test-key");
  const composer = page.getByLabel("Message", { exact: true });
  await composer.fill("Explain the zeta initializer startup sequence in src/app.py.");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Deterministic answer: the zeta initializer prepares the startup state.", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("src/app.py", { exact: false }).first()).toBeVisible();

  const failedDraft = "E2E_FAIL_MODEL keep this text as a draft";
  await composer.fill(failedDraft);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByRole("alert")).toContainText("could not complete this request", { timeout: 30_000 });
  await expect(composer).toHaveValue(failedDraft);

  await page.reload();
  await expect(page.getByRole("heading", { name: "E2E Repo One Updated", level: 1 })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Deterministic answer: the zeta initializer prepares the startup state.", { exact: true })).toBeVisible();
  await expect(page.getByText(failedDraft, { exact: true })).toHaveCount(0);
  await page.getByLabel("Your OpenAI API key").fill("e2e-only-test-key");

  await page.getByRole("button", { name: "Illustrate" }).click();
  await page.getByLabel("Message", { exact: true }).fill("Illustrate the zeta initializer startup sequence in src/app.py.");
  await page.getByRole("button", { name: "Send message" }).click();
  const illustration = page.locator("figure.bot-illustration");
  await expect(illustration).toBeVisible({ timeout: 60_000 });
  await expect(illustration.locator("img")).toBeVisible({ timeout: 60_000 });
  await expect(illustration.locator("img")).toHaveAttribute("src", /^blob:/);
  const desktopScreenshot = testInfo.outputPath("e2e-populated-chat-desktop.png");
  await page.screenshot({ path: desktopScreenshot, fullPage: true });
  await testInfo.attach("e2e-populated-chat-desktop.png", {
    path: desktopScreenshot,
    contentType: "image/png",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  )).toBe(true);
  const mobileScreenshot = testInfo.outputPath("e2e-populated-chat-mobile.png");
  await page.screenshot({ path: mobileScreenshot, fullPage: true });
  await testInfo.attach("e2e-populated-chat-mobile.png", {
    path: mobileScreenshot,
    contentType: "image/png",
  });
  await page.setViewportSize({ width: 1280, height: 720 });

  await page.getByRole("button", { name: "Code changes" }).click();
  await page.getByLabel("What should change?").fill("Update the README documentation title and explain the zeta initializer.");
  await page.getByRole("button", { name: "Propose change" }).click();
  const proposal = page.locator(".bot-change-card").filter({ hasText: "Clarify the fixture README" });
  await expect(proposal).toBeVisible({ timeout: 30_000 });
  await expect(proposal).toContainText("README.md");
  await proposal.getByRole("button", { name: "Apply on branch" }).click();
  await expect(proposal.locator(".bot-change-status")).toHaveText("applied", { timeout: 60_000 });
  await expect(page.locator(".bot-tool-panel")).toContainText("Change applied on its branch.");

  const repoTwo = `${storageDir}/e2e-fixtures/${runId}/repo-two`;
  await page.getByRole("button", { name: "Back to bots" }).click();
  await createBot(page, repoTwo, "repo-two", "E2E Repo Two", "e2e-browser-model");
  await expect(page.getByRole("heading", { name: "E2E Repo Two", level: 1 })).toBeVisible({ timeout: 180_000 });
  const secondBotUrl = page.url();
  await expect(page.getByText("Your conversations will appear here.")).toBeVisible();
  await expect(page.getByText("Deterministic answer: the zeta initializer prepares the startup state.", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByText("Start a conversation")).toBeVisible();
  await page.getByLabel("Your OpenAI API key").fill("e2e-only-test-key");
  const secondComposer = page.getByLabel("Message", { exact: true });
  await secondComposer.fill("SECOND_BOT_MARKER: explain zeta initializer from src/app.py");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText("Deterministic answer for SECOND_BOT_MARKER.", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.goto(firstBotUrl);
  await expect(page.getByRole("heading", { name: "E2E Repo One Updated", level: 1 })).toBeVisible();
  await expect(page.getByText("Deterministic answer for SECOND_BOT_MARKER.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Deterministic answer: the zeta initializer prepares the startup state.", { exact: true }).first()).toBeVisible();
  expect(secondBotUrl).not.toBe(firstBotUrl);
});

async function createBot(
  page: import("@playwright/test").Page,
  repositoryPath: string,
  displayName: string,
  botName: string,
  model: string,
): Promise<void> {
  await page.getByRole("button", { name: "+ Add a repository" }).click();
  await page.getByLabel("Local folder or Git URL").fill(repositoryPath);
  await page.getByLabel(/^Display name/).fill(displayName);
  await page.getByLabel("Bot name").fill(botName);
  await page.getByLabel("OpenAI model ID").fill(model);
  await page.getByRole("button", { name: "Create bot" }).click();
}

