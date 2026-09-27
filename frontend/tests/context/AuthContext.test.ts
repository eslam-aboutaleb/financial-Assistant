import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/context/AuthContext";

describe("AuthContext", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("starts in loading state", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.status).toBe("loading");
  });

  it("hydrates to unauthenticated when no token", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: "Sign in to continue" }),
      } as Response),
    );

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    expect(result.current.status).toBe("unauthenticated");
    expect(result.current.token).toBeNull();
    expect(result.current.userId).toBeNull();
  });

  it("login sets token, userId and authenticated status", async () => {
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
        status: 401,
        json: () => Promise.resolve({ detail: "Sign in to continue" }),
      } as Response);
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    act(() => {
      result.current.login("fake-token", "user-123");
    });

    expect(result.current.token).toBe("fake-token");
    expect(result.current.userId).toBe("user-123");
    expect(result.current.status).toBe("authenticated");
  });

  it("logout clears state and sets unauthenticated", async () => {
    let meCallCount = 0;
    global.fetch = vi.fn((url: string, options?: RequestInit) => {
      if (url.includes("/api/v1/auth/me")) {
        meCallCount += 1;
        const authHeader = options?.headers?.["Authorization"];
        if (meCallCount > 1 && !authHeader) {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: () => Promise.resolve({ detail: "Sign in to continue" }),
          } as Response);
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ user_id: "user-123" }),
        } as Response);
      }
      if (url.includes("/api/v1/auth/logout")) {
        return Promise.resolve({
          ok: true,
          status: 204,
          json: () => Promise.resolve({}),
        } as Response);
      }
      return Promise.resolve({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: "Sign in to continue" }),
      } as Response);
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => expect(result.current.status).not.toBe("loading"));

    act(() => {
      result.current.login("fake-token", "user-123");
    });

    expect(result.current.status).toBe("authenticated");

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.token).toBeNull();
    expect(result.current.userId).toBeNull();
    expect(result.current.status).toBe("unauthenticated");
  });
});
