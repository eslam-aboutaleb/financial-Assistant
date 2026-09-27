import { test, expect } from "@playwright/test";

test("homepage loads", async ({ page }) => {
  await page.goto("http://localhost:3000/chat");
  await expect(page.locator("#root")).toBeVisible();
  await expect(page.locator("#chat-window")).toBeVisible();
});
