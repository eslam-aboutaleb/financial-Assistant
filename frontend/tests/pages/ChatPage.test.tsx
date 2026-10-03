import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";
import {
  MemoryRouter,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import ChatPage from "@/pages/ChatPage";

const CONVERSATIONS = [
  {
    id: "aaaaaaaa-1111-1111-1111-111111111111",
    title: "Old convo about water damage",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "bbbbbbbb-2222-2222-2222-222222222222",
    title: "Old convo about filing a claim",
    created_at: "2024-01-02T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
  },
];

const MESSAGES: Record<
  string,
  { id: string; role: string; content: string; timestamp: string }[]
> = {
  "aaaaaaaa-1111-1111-1111-111111111111": [
    {
      id: "m1",
      role: "user",
      content: "Is water damage covered?",
      timestamp: "2024-01-01T00:00:00Z",
    },
    {
      id: "m2",
      role: "assistant",
      content: "Water damage is covered for sudden events.",
      timestamp: "2024-01-01T00:00:01Z",
    },
  ],
  "bbbbbbbb-2222-2222-2222-222222222222": [
    {
      id: "m3",
      role: "user",
      content: "How do I file a claim?",
      timestamp: "2024-01-02T00:00:00Z",
    },
  ],
};

const JWT = "header.payload.signature";

function currentPath(): string {
  return screen.getByTestId("current-path").textContent ?? "";
}

function installFetch(): void {
  global.fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/api/v1/auth/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ user_id: "user-123" }),
      } as Response);
    }
    if (url.endsWith("/api/v1/chat/conversations")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ conversations: CONVERSATIONS }),
      } as Response);
    }
    const detail = url.match(/\/api\/v1\/chat\/conversations\/([^/?#]+)/);
    if (detail) {
      const id = detail[1];
      const meta = CONVERSATIONS.find((c) => c.id === id);
      if (!meta) {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: "Conversation not found" }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...meta, messages: MESSAGES[id] ?? [] }),
      } as Response);
    }
    if (url.endsWith("/api/v1/chat/reset") && init?.method === "POST") {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    } as Response);
  }) as unknown as typeof fetch;
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="current-path">{location.pathname}</div>;
}

/** Renders ChatPage and lets a test drive navigation the way a browser would. */
function NavigationBridge({
  onReady,
}: {
  onReady: (navigate: (to: string) => void) => void;
}) {
  const navigate = useNavigate();
  onReady(navigate);
  return null;
}

function renderChatPage(initialEntry = "/chat") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  let navigate: (to: string) => void = () => {};

  const utils = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <LocationProbe />
          <NavigationBridge onReady={(n) => (navigate = n)} />
          <Routes>
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:conversationId" element={<ChatPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  return { ...utils, queryClient, navigateTo: (to: string) => navigate(to) };
}

beforeEach(() => {
  window.localStorage.setItem("omnicare_token", JWT);
  window.localStorage.setItem("omnicare_user_id", "user-123");
  installFetch();
});

describe("ChatPage conversation sidebar navigation", () => {
  it("lists the current user's old conversations in the sidebar", async () => {
    renderChatPage("/chat");

    const history = await screen.findByTestId("chat-history");
    await waitFor(() => {
      expect(history.querySelectorAll("button")).toHaveLength(
        CONVERSATIONS.length,
      );
    });
    expect(
      screen.getByText("Old convo about water damage"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Old convo about filing a claim"),
    ).toBeInTheDocument();
    expect(screen.queryByText("No conversations yet")).not.toBeInTheDocument();
  });

  it("navigates to /chat/:conversationId and loads history when a conversation is clicked", async () => {
    renderChatPage("/chat");

    fireEvent.click(await screen.findByText("Old convo about filing a claim"));

    await waitFor(() => {
      expect(currentPath()).toBe("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });
    await waitFor(() => {
      expect(screen.getByText("How do I file a claim?")).toBeInTheDocument();
    });
  });

  it("keeps every old conversation reachable from any conversation", async () => {
    renderChatPage("/chat");

    fireEvent.click(await screen.findByText("Old convo about water damage"));
    await waitFor(() =>
      expect(currentPath()).toBe("/chat/aaaaaaaa-1111-1111-1111-111111111111"),
    );

    const history = screen.getByTestId("chat-history");
    expect(history.querySelectorAll("button")).toHaveLength(
      CONVERSATIONS.length,
    );
    expect(
      screen.getByText("Old convo about filing a claim"),
    ).toBeInTheDocument();
  });

  it("swaps the loaded history when a different conversation is clicked", async () => {
    renderChatPage("/chat");

    fireEvent.click(await screen.findByText("Old convo about water damage"));
    await waitFor(() => {
      expect(screen.getByText("Is water damage covered?")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Old convo about filing a claim"));
    await waitFor(() => {
      expect(currentPath()).toBe("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });
    await waitFor(() => {
      expect(screen.getByText("How do I file a claim?")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Is water damage covered?"),
    ).not.toBeInTheDocument();
  });

  it("remounts the chat window when the route changes without a sidebar click", async () => {
    const { navigateTo } = renderChatPage("/chat");

    fireEvent.click(await screen.findByText("Old convo about water damage"));
    await waitFor(() => {
      expect(screen.getByText("Is water damage covered?")).toBeInTheDocument();
    });

    act(() => {
      navigateTo("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });

    await waitFor(() => {
      expect(currentPath()).toBe("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });
    await waitFor(() => {
      expect(screen.getByText("How do I file a claim?")).toBeInTheDocument();
    });
    expect(
      screen.queryByText("Is water damage covered?"),
    ).not.toBeInTheDocument();
  });

  it("does not leak the previous conversation's scroll state on a route-only change", async () => {
    const { navigateTo } = renderChatPage("/chat");

    fireEvent.click(await screen.findByText("Old convo about water damage"));
    await waitFor(() => {
      expect(screen.getByText("Is water damage covered?")).toBeInTheDocument();
    });

    const scroller = screen.getByTestId("messages-container");
    Object.defineProperty(scroller, "scrollHeight", {
      configurable: true,
      value: 1000,
    });
    Object.defineProperty(scroller, "clientHeight", {
      configurable: true,
      value: 400,
    });
    fireEvent.scroll(scroller, { target: { scrollTop: 0 } });

    await screen.findByRole("button", { name: "Scroll to bottom" });

    act(() => {
      navigateTo("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });

    await waitFor(() => {
      expect(currentPath()).toBe("/chat/bbbbbbbb-2222-2222-2222-222222222222");
    });
    await waitFor(() => {
      expect(screen.getByText("How do I file a claim?")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Scroll to bottom" }),
    ).not.toBeInTheDocument();
  });

  it("loads history on a direct deep link to an old conversation", async () => {
    renderChatPage("/chat/aaaaaaaa-1111-1111-1111-111111111111");

    expect(currentPath()).toBe("/chat/aaaaaaaa-1111-1111-1111-111111111111");
    await waitFor(() => {
      expect(screen.getByText("Is water damage covered?")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Water damage is covered for sudden events."),
    ).toBeInTheDocument();
  });

  it("keeps the old conversations listed and clears history on New Chat", async () => {
    renderChatPage("/chat/aaaaaaaa-1111-1111-1111-111111111111");
    await waitFor(() => {
      expect(screen.getByText("Is water damage covered?")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("new-chat-button"));

    await waitFor(() => expect(currentPath()).toBe("/chat"));
    expect(
      screen.queryByText("Is water damage covered?"),
    ).not.toBeInTheDocument();
    const history = await screen.findByTestId("chat-history");
    await waitFor(() => {
      expect(history.querySelectorAll("button")).toHaveLength(
        CONVERSATIONS.length,
      );
    });
  });
});
