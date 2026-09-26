/**
 * Providers component.
 *
 * Wraps the entire React application in the context providers and query
 * client required by the client-side features.
 *
 * Provider stack (innermost to outermost):
 *   1. ``AuthProvider`` -- Manages JWT session state and localStorage persistence.
 *   2. ``QueryClientProvider`` -- Provides the React Query client for data
 *      fetching, caching, and background refetching.
 *
 * This component is rendered in the root layout and should not be imported
 * or used elsewhere.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useState } from "react";
import { AuthProvider } from "@/context/AuthContext";

export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Stale time of 1 minute means data is considered fresh for 60s
            // after a successful fetch. This reduces unnecessary refetches
            // when users navigate between the sidebar and chat window.
            staleTime: 1000 * 60,
            // Retry failed queries up to 3 times before surfacing the error
            // to the UI. This handles transient network blips gracefully.
            retry: 3,
          },
          mutations: {
            // Mutations are not retried by default because they often have
            // side effects (sending a chat message, creating a conversation).
            // We only retry reads (queries), not writes (mutations).
            retry: 3,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
