import { test, expect } from '@playwright/test';

test.describe('Baseline Chat Tests', () => {
  test('authenticated user sees empty chat', async ({ page }) => {
    // Mock successful login
    await page.route('**/api/v1/auth/signin', async route => {
      await route.fulfill({ status: 200, json: { access_token: 'mock-token', user_id: 'mock-user' } });
    });
    // Mock chat sessions (empty)
    await page.route('**/api/v1/chat/conversations', async route => {
      await route.fulfill({ status: 200, json: { data: [] } });
    });
    
    await page.goto('/');
    
    // Fill in auth modal
    await page.getByPlaceholder('Enter your email').fill('test@example.com');
    await page.getByPlaceholder('Enter your password').fill('password123');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();

    // Wait for chat input to be visible
    const chatInput = page.getByPlaceholder('Ask about coverage, claims, deductibles, or policy details...');
    await expect(chatInput).toBeVisible({ timeout: 10000 });
    
    // Hide typing indicators or dynamic stuff if any before screenshot
    await page.waitForTimeout(1000);

    // Take screenshot of empty chat
    await expect(page).toHaveScreenshot('chat-empty.png', {
      fullPage: true,
      animations: 'disabled'
    });
  });
});
