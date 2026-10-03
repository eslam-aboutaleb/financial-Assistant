import { test, expect } from "@playwright/test";

const API_URL = "http://localhost:8000";
const APP_URL = "http://localhost:3000";
const PASSWORD = "TestPass123!";

type Conversation = { id: string; title: string };

/**
 * Creates a user with two conversations by driving the real chat API, so the
 * browser assertions below run against genuine backend data.
 */
async function seedUserWithTwoConversations(request: any) {
  const username = `sidebar_e2e_${Date.now()}${Math.floor(Math.random() * 1e6)}@example.com`;

  const signup = await request.post(`${API_URL}/api/v1/auth/signup`, {
    data: { username, password: PASSWORD },
  });
  expect(signup.status()).toBe(201);
  const token = (await signup.json()).access_token;
  const headers = { Authorization: `Bearer ${token}` };

  const send = async (message: string) => {
    const response = await request.post(`${API_URL}/api/v1/chat/stream`, {
      data: { message },
      headers,
    });
    expect(response.status()).toBe(200);
  };

  await send("First archived conversation about water damage");
  await request.post(`${API_URL}/api/v1/chat/reset`, { headers });
  await send("Second archived conversation about filing a claim");

  // Persistence happens after the stream closes.
  await expect
    .poll(
      async () => {
        const list = await request.get(`${API_URL}/api/v1/chat/conversations`, {
          headers,
        });
        return ((await list.json()).conversations as Conversation[]).length;
      },
      { timeout: 30_000 },
    )
    .toBe(2);

  const list = await request.get(`${API_URL}/api/v1/chat/conversations`, {
    headers,
  });
  const conversations = (await list.json()).conversations as Conversation[];

  return { username, conversations };
}

async function signIn(page: any, username: string) {
  await page.goto(`${APP_URL}/login`);
  await page.getByPlaceholder("Enter your email").fill(username);
  await page.getByPlaceholder("Enter your password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/chat**", { timeout: 30_000 });
}

test("old conversations stay listed in the sidebar and open at /chat/:id", async ({
  page,
  request,
}) => {
  const { username, conversations } =
    await seedUserWithTwoConversations(request);
  const [newest, oldest] = conversations;

  await signIn(page, username);

  const history = page.getByTestId("chat-history");
  await expect(history.getByRole("button")).toHaveCount(2);
  await expect(history).not.toContainText("No conversations yet");
  await expect(history).toContainText(newest.title);
  await expect(history).toContainText(oldest.title);

  await history.getByText(oldest.title).click();

  await expect(page).toHaveURL(`${APP_URL}/chat/${oldest.id}`);
  await expect(
    page.getByText("This is an archived chat", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("First archived conversation about water damage"),
  ).toBeVisible();

  // A full page load on the deep link must still resolve the conversation.
  await page.reload();
  await expect(page).toHaveURL(`${APP_URL}/chat/${oldest.id}`);
  await expect(
    page.getByText("First archived conversation about water damage"),
  ).toBeVisible();

  // Both conversations remain reachable, and the other one loads its own history.
  await page.getByTestId("chat-history").getByText(newest.title).click();
  await expect(page).toHaveURL(`${APP_URL}/chat/${newest.id}`);
  await expect(
    page.getByText("Second archived conversation about filing a claim"),
  ).toBeVisible();
  await expect(
    page.getByText("First archived conversation about water damage"),
  ).toHaveCount(0);
});

test("New Chat clears the view but keeps old conversations in the sidebar", async ({
  page,
  request,
}) => {
  const { username, conversations } =
    await seedUserWithTwoConversations(request);

  await signIn(page, username);

  const history = page.getByTestId("chat-history");
  await expect(history.getByRole("button")).toHaveCount(2);

  await history.getByText(conversations[0].title).click();
  await expect(page).toHaveURL(`${APP_URL}/chat/${conversations[0].id}`);

  await page.getByTestId("new-chat-button").click();

  await expect(page).toHaveURL(`${APP_URL}/chat`);
  await expect(history.getByRole("button")).toHaveCount(2);
  await expect(history).toContainText(conversations[1].title);
});
