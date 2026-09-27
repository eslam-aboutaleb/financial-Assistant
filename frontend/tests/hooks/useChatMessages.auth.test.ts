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

describe("useChatMessages auth error handling", () => {
  const onNewChat = vi.fn();
  const onMessageSent = vi.fn();
  const onAuthError = vi.fn();

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
      if (url.includes("/api/v1/chat")) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({
              detail: "Session expired. Please log in again.",
            }),
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: "Server error" }),
      } as Response);
    });
  });

  it("calls onAuthError when stream throws 401", async () => {
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

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));
    });

    expect(onAuthError).toHaveBeenCalled();
  });
});
