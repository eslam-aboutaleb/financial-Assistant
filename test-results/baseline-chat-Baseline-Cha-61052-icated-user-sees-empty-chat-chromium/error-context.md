# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: baseline/chat.spec.ts >> Baseline Chat Tests >> authenticated user sees empty chat
- Location: tests/migration/baseline/chat.spec.ts:4:7

# Error details

```
Error: expect(page).toHaveScreenshot(expected) failed

  19374 pixels (ratio 0.03 of all image pixels) are different.

  Snapshot: chat-empty.png

Call log:
  - Expect "toHaveScreenshot(chat-empty.png)" with timeout 5000ms
    - verifying given screenshot expectation
  - taking page screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - 19374 pixels (ratio 0.03 of all image pixels) are different.
  - waiting 100ms before taking screenshot
  - taking page screenshot
    - disabled all CSS animations
  - waiting for fonts to load...
  - fonts loaded
  - captured a stable screenshot
  - 19374 pixels (ratio 0.03 of all image pixels) are different.

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - main [ref=e3]:
    - generic "Navigation sidebar" [ref=e5]:
      - generic [ref=e11]:
        - generic [ref=e12]: OmniCare
        - generic [ref=e13]: Policy & Claims Assistant
      - button "Start a new chat" [ref=e15] [cursor=pointer]:
        - generic [ref=e17]: New Chat
      - generic "Chat history" [ref=e18]:
        - generic [ref=e19]: Conversations
        - generic [ref=e20]:
          - generic [ref=e21]: No conversations yet
          - generic [ref=e22]: Your conversations will appear here.
      - button "Logout" [ref=e24] [cursor=pointer]
      - generic [ref=e29]: OmniCare Policy & Claims Assistant v1.0
    - generic [ref=e30]:
      - button "Open menu" [ref=e32] [cursor=pointer]
      - generic "Chat window" [ref=e35]:
        - generic [ref=e37]:
          - generic [ref=e42]:
            - heading "Welcome to OmniCare" [level=2] [ref=e43]
            - paragraph [ref=e44]: Ask about your coverage, claims, policy details, or start a new claim.
          - generic [ref=e45]:
            - button "Check my recent claims" [ref=e46] [cursor=pointer]
            - button "What does my policy cover?" [ref=e47] [cursor=pointer]
            - button "File a new claim" [ref=e48] [cursor=pointer]
        - generic [ref=e50]:
          - generic [ref=e51]:
            - textbox "Chat message input" [ref=e52]:
              - /placeholder: Ask about coverage, claims, deductibles, or policy details...
            - button "Send message" [disabled] [ref=e53]
          - generic [ref=e57]: AI-generated information. Verify important coverage and claim details against your policy or insurer.
  - status [ref=e64]: Successfully signed in!
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('Baseline Chat Tests', () => {
  4  |   test('authenticated user sees empty chat', async ({ page }) => {
  5  |     // Mock successful login
  6  |     await page.route('**/api/v1/auth/signin', async route => {
  7  |       await route.fulfill({ status: 200, json: { access_token: 'mock-token', user_id: 'mock-user' } });
  8  |     });
  9  |     // Mock chat sessions (empty)
  10 |     await page.route('**/api/v1/chat/conversations', async route => {
  11 |       await route.fulfill({ status: 200, json: { data: [] } });
  12 |     });
  13 |     
  14 |     await page.goto('/');
  15 |     
  16 |     // Fill in auth modal
  17 |     await page.getByPlaceholder('Enter your email').fill('test@example.com');
  18 |     await page.getByPlaceholder('Enter your password').fill('password123');
  19 |     await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  20 | 
  21 |     // Wait for chat input to be visible
  22 |     const chatInput = page.getByPlaceholder('Ask about coverage, claims, deductibles, or policy details...');
  23 |     await expect(chatInput).toBeVisible({ timeout: 10000 });
  24 |     
  25 |     // Hide typing indicators or dynamic stuff if any before screenshot
  26 |     await page.waitForTimeout(1000);
  27 | 
  28 |     // Take screenshot of empty chat
> 29 |     await expect(page).toHaveScreenshot('chat-empty.png', {
     |                        ^ Error: expect(page).toHaveScreenshot(expected) failed
  30 |       fullPage: true,
  31 |       animations: 'disabled'
  32 |     });
  33 |   });
  34 | });
  35 | 
```