import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  const testEmail = `testuser_${Date.now()}@example.com`;
  const testPassword = 'password123';

  test('should successfully sign up with an email and then sign in', async ({ page }) => {
    // Navigate to the app (assuming it runs on localhost:3000)
    await page.goto('http://localhost:3000/');

    // Open Auth Modal by clicking a Sign In / Get Started button
    // The exact button selector depends on the app, let's look for "Sign In" or similar
    const signInButton = page.locator('button', { hasText: /Sign In|Get Started|Login/i }).first();
    if (await signInButton.isVisible()) {
      await signInButton.click();
    } else {
      console.log("No explicit sign-in button found on the main page; perhaps the modal is already open or we're redirected.");
    }

    // Ensure the AuthModal is visible
    const authModal = page.locator('.fixed.inset-0', { hasText: 'Sign In' }).or(page.locator('.fixed.inset-0', { hasText: 'Create an Account' }));
    await authModal.waitFor({ state: 'visible', timeout: 5000 });

    // Switch to Sign Up mode
    const toggleToSignUp = page.locator('button', { hasText: "Don't have an account? Sign up" });
    if (await toggleToSignUp.isVisible()) {
      await toggleToSignUp.click();
    }

    // Verify we are in Sign Up mode
    await expect(page.locator('h2')).toContainText('Create an Account');

    // Fill the sign up form
    await page.fill('input[placeholder="Enter username or email"]', testEmail);
    await page.fill('input[placeholder="Enter password"]', testPassword);

    // Submit
    await page.click('button[type="submit"]');

    // Expect success toast
    await expect(page.locator('text=Successfully signed up!')).toBeVisible({ timeout: 10000 });

    // Wait for redirection or modal close, perhaps we are now logged in
    await authModal.waitFor({ state: 'hidden', timeout: 10000 });

    // Now let's try signing in. We may need to log out first.
    // If there is a sign out / logout button, click it
    const logoutButton = page.locator('button', { hasText: /Sign Out|Logout/i }).first();
    if (await logoutButton.isVisible({ timeout: 5000 })) {
      await logoutButton.click();
    } else {
      // Maybe we can just clear cookies and reload to force logged out state
      await page.context().clearCookies();
      await page.reload();
    }

    // Re-open Auth Modal
    const signInButtonAgain = page.locator('button', { hasText: /Sign In|Get Started|Login/i }).first();
    if (await signInButtonAgain.isVisible()) {
      await signInButtonAgain.click();
    }

    // Ensure we are in Sign In mode
    const toggleToSignIn = page.locator('button', { hasText: "Already have an account? Sign in" });
    if (await toggleToSignIn.isVisible()) {
      await toggleToSignIn.click();
    }

    await expect(page.locator('h2')).toContainText('Sign In');

    // Fill the sign in form with the same email
    await page.fill('input[placeholder="Enter username or email"]', testEmail);
    await page.fill('input[placeholder="Enter password"]', testPassword);

    // Submit
    await page.click('button[type="submit"]');

    // Expect success toast
    await expect(page.locator('text=Successfully signed in!')).toBeVisible({ timeout: 10000 });
  });
});
