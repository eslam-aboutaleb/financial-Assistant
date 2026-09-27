import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import React from "react";
import { useChatMessages } from "@/hooks/useChatMessages";
import { AuthProvider } from "@/context/AuthContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient();

const createWrapper = () => {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(AuthProvider, null, children),
    );
};

beforeEach(() => {
  window.localStorage.setItem("omnicare_token", "fake-token");
  window.localStorage.setItem("omnicare_user_id", "user-123");
  global.fetch = vi.fn((url: string) => {
    if (url.includes("/api/v1/auth/me")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ user_id: "user-123" }),
      } as Response);
    }
    return Promise.resolve({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "Server error" }),
    } as Response);
  });
});

describe("useChatMessages", () => {
  const onNewChat = vi.fn();
  const onMessageSent = vi.fn();
  const onAuthError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("adds user message then assistant message on send", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.handleSendMessage("Hello");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("Hello");
    expect(result.current.messages[1].role).toBe("assistant");
  });

  it("does not send empty message", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.handleSendMessage("   ");
    });

    expect(result.current.messages).toHaveLength(0);
  });

  it("isStreaming is true while message is being sent", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.handleSendMessage("Hello");
    });

    expect(result.current.isStreaming).toBe(true);
  });

  it("handleStopGeneration stops streaming", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => {
      result.current.handleSendMessage("Hello");
    });

    expect(result.current.isStreaming).toBe(true);

    act(() => {
      result.current.handleStopGeneration();
    });

    expect(result.current.isStreaming).toBe(false);
  });

  it("isReadOnly is true when historyId is set", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          historyId: "some-id",
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.isReadOnly).toBe(true);
  });

  it("isReadOnly is false when historyId is not set", async () => {
    const { result } = renderHook(
      () =>
        useChatMessages({
          onNewChat,
          onMessageSent,
          onAuthError,
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.isReadOnly).toBe(false);
  });
});
