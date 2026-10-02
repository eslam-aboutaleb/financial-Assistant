import { describe, it, expect, vi, beforeEach } from "vitest";
import { ComponentProps, FormEvent } from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import Sidebar from "@/components/Sidebar";

const CONVERSATIONS = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Old convo about water damage",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    title: "Old convo about filing a claim",
    created_at: "2024-01-02T00:00:00Z",
    updated_at: "2024-01-02T00:00:00Z",
  },
  {
    id: "33333333-3333-3333-3333-333333333333",
    title: "Old convo about policy limits",
    created_at: "2024-01-03T00:00:00Z",
    updated_at: "2024-01-03T00:00:00Z",
  },
];

const JWT = "header.payload.signature";

function mockFetch(
  conversations: unknown[] = CONVERSATIONS,
  status = 200,
): void {
  global.fetch = vi.fn((url: string) => {
    if (url.includes("/api/v1/auth/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ user_id: "user-123" }),
      } as Response);
    }
    if (url.endsWith("/api/v1/chat/conversations")) {
      return Promise.resolve({
        ok: status === 200,
        status,
        json: () => Promise.resolve({ conversations }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    } as Response);
  }) as unknown as typeof fetch;
}

function renderSidebar(props: Partial<ComponentProps<typeof Sidebar>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const onSelectChat = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Sidebar onNewChat={vi.fn()} onSelectChat={onSelectChat} {...props} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return { onSelectChat, queryClient };
}

beforeEach(() => {
  window.localStorage.setItem("omnicare_token", JWT);
  window.localStorage.setItem("omnicare_user_id", "user-123");
  mockFetch();
});

describe("Sidebar conversation history", () => {
  it("renders every conversation returned by the API, not just new ones", async () => {
    renderSidebar();

    const history = screen.getByTestId("chat-history");
    await waitFor(() => {
      expect(history.querySelectorAll("button")).toHaveLength(
        CONVERSATIONS.length,
      );
    });

    for (const conversation of CONVERSATIONS) {
      expect(screen.getByText(conversation.title)).toBeInTheDocument();
    }
  });

  it("does not show the empty-state placeholder when conversations exist", async () => {
    renderSidebar();

    await screen.findByText("Old convo about water damage");
    expect(screen.queryByText("No conversations yet")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Your conversations will appear here."),
    ).not.toBeInTheDocument();
  });

  it("keeps old conversations visible after refreshTrigger changes", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Sidebar
            onNewChat={vi.fn()}
            onSelectChat={vi.fn()}
            refreshTrigger={0}
          />
        </AuthProvider>
      </QueryClientProvider>,
    );

    await screen.findByText("Old convo about water damage");

    rerender(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Sidebar
            onNewChat={vi.fn()}
            onSelectChat={vi.fn()}
            refreshTrigger={1}
          />
        </AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Old convo about water damage")).toBeInTheDocument();
    });
    expect(screen.getByText("Old convo about filing a claim")).toBeInTheDocument();
  });

  it("calls onSelectChat with the clicked conversation id", async () => {
    const { onSelectChat } = renderSidebar();

    fireEvent.click(
      await screen.findByText("Old convo about filing a claim"),
    );

    expect(onSelectChat).toHaveBeenCalledTimes(1);
    expect(onSelectChat).toHaveBeenCalledWith(
      "22222222-2222-2222-2222-222222222222",
    );
  });

  it("marks the active conversation using activeConversationId", async () => {
    renderSidebar({
      activeConversationId: "33333333-3333-3333-3333-333333333333",
    });

    const active = await screen.findByText("Old convo about policy limits");
    const activeButton = active.closest("button");
    const inactiveButton = screen
      .getByText("Old convo about water damage")
      .closest("button");

    expect(activeButton?.className).toContain("bg-insurance-border");
    expect(inactiveButton?.className).not.toContain("bg-insurance-border");
  });

  it("declares type=button on every sidebar button so clicks never submit a wrapping form", async () => {
    const onNewChat = vi.fn();
    const onLogout = vi.fn();
    renderSidebar({ onNewChat, onLogout });

    await screen.findByText("Old convo about water damage");

    const buttons = Array.from(
      document.querySelectorAll<HTMLButtonElement>(
        '[data-testid="sidebar"] button',
      ),
    );
    expect(buttons.length).toBeGreaterThanOrEqual(CONVERSATIONS.length + 1);
    for (const button of buttons) {
      expect(button.getAttribute("type")).toBe("button");
    }
  });

  it("does not submit a surrounding form when a conversation is clicked", async () => {
    const onSubmit = vi.fn((e: FormEvent) => e.preventDefault());
    const onSelectChat = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <form onSubmit={onSubmit}>
            <Sidebar onNewChat={vi.fn()} onSelectChat={onSelectChat} />
          </form>
        </AuthProvider>
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByText("Old convo about water damage"));

    expect(onSelectChat).toHaveBeenCalledWith(
      "11111111-1111-1111-1111-111111111111",
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows the empty state only when the user truly has no conversations", async () => {
    mockFetch([]);
    renderSidebar();

    expect(await screen.findByText("No conversations yet")).toBeInTheDocument();
  });
});
