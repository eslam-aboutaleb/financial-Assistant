import { test, expect } from '@playwright/test';

test.describe('Baseline UI Tests', () => {
  test('unauthenticated user sees AuthModal', async ({ page }) => {
    // Mock the session endpoint to return 401 Unauthenticated
    await page.route('**/api/v1/auth/session', async route => {
      await route.fulfill({ status: 401, json: { error: 'Unauthorized' } });
    });

    await page.goto('/');
    
    // Check if the AuthModal is visible
    const emailInput = page.getByPlaceholder('Enter your email');
    await expect(emailInput).toBeVisible();
    
    // Take a screenshot of the login page
    await expect(page).toHaveScreenshot('login-empty.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });
});
