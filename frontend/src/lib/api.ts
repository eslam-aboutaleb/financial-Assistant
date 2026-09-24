import { ChatResponse } from "../types/chat";

// ── Idempotency key generation ──────────────────────────────────────────────
function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

// ── Retry configuration ─────────────────────────────────────────────────────
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1_000;
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);

function isRetryableError(status: number): boolean {
  return RETRYABLE_STATUS_CODES.has(status);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Main API function ────────────────────────────────────────────────────────

/**
 * Send a chat message to the OmniCare backend with automatic idempotent retry.
 *
 * On network errors or transient server errors (5xx, 429, 408) the request is
 * retried up to MAX_RETRIES times using exponential backoff. The same
 * Idempotency-Key is sent on every attempt so the server deduplicates them --
 * the LLM agent runs exactly once even if the client retries multiple times.
 */
export async function sendMessage(
  token: string | null,
  message: string,
): Promise<ChatResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const idempotencyKey = generateIdempotencyKey();

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = RETRY_DELAY_MS * Math.pow(2, attempt - 1);
      await sleep(delay);
    }

    let response: Response;
    try {
      response = await fetch(`${apiUrl}/api/v1/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message }),
      });
    } catch (err) {
      // Network-level error (fetch threw)
      if (attempt === MAX_RETRIES) {
        throw err instanceof Error ? err : new Error(String(err));
      }
      lastError = err instanceof Error ? err : new Error(String(err));
      console.warn(
        `[api] Attempt ${attempt + 1}/${MAX_RETRIES + 1} failed (network error). Retrying...`,
      );
      continue;
    }

    if (response.ok) {
      return response.json();
    }

    // Parse error response for a user-friendly message
    let errorMessage = "Failed to send message. Please try again.";
    try {
      const errorData = await response.json();
      if (errorData.error?.message) {
        errorMessage = errorData.error.message;
      } else if (errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      // Body was not JSON -- use generic message
    }

    if (!isRetryableError(response.status) || attempt === MAX_RETRIES) {
      throw new Error(errorMessage);
    }

    lastError = new Error(errorMessage);
    console.warn(
      `[api] Attempt ${attempt + 1}/${MAX_RETRIES + 1} failed (HTTP ${response.status}). Retrying...`,
    );
  }

  throw (
    lastError ?? new Error("Failed to send message after multiple retries.")
  );
}

/**
 * Reset the authenticated user's conversation session on the backend.
 * This clears the agent's in-memory conversation history so the next
 * message starts with a fresh context.
 */
export async function resetChat(token: string | null): Promise<void> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  await fetch(`${apiUrl}/api/v1/chat/reset`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}
