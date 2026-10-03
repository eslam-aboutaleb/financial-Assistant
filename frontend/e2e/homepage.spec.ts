import { test, expect } from "@playwright/test";

test("homepage loads", async ({ page }) => {
  await page.goto("http://localhost:3000/chat");
  await expect(page.locator("#root")).toBeVisible();
});

test("unauthenticated /chat redirects to the login page", async ({ page }) => {
  await page.goto("http://localhost:3000/chat");
  await expect(page).toHaveURL("http://localhost:3000/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("unauthenticated deep link redirects to the login page", async ({
  page,
}) => {
  await page.goto(
    "http://localhost:3000/chat/6c9984c6-d9dd-4fd6-a19c-678d83bbc9c0",
  );
  await expect(page).toHaveURL("http://localhost:3000/login");
});
