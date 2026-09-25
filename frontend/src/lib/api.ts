/**
 * API client functions for communicating with the OmniCare FastAPI backend.
 *
 * This module centralizes all HTTP requests to the backend, including
 * authentication header injection, idempotency key generation, and error
 * normalization. Components should import from here rather than calling
 * ``fetch`` directly to ensure consistent request handling.
 *
 * Environment:
 *   The backend URL is read from ``VITE_API_URL``. In development,
 *   this defaults to ``http://localhost:8000``. In production, set this to
 *   the deployed backend origin.
 */

import { ChatResponse, ADKSSEEvent } from "@/types/chat";

/**
 * Generate a cryptographically random idempotency key.
 *
 * Uses ``crypto.randomUUID`` when available (modern browsers and Node 19+),
 * falling back to a timestamp + random string for older environments.
 *
 * The key is sent as the ``Idempotency-Key`` header on chat requests so
 * that the backend can deduplicate retries without affecting legitimate
 * repeated requests (we do NOT key on user_id + message).
 */
function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Send a chat message to the OmniCare backend.
 *
 * Automatically generates an idempotency key for safe retries. The backend
 * caches the response for this key, so network retries (handled by React
 * Query) will not trigger duplicate LLM calls.
 *
 * @param token - The JWT access token for authentication, or null for
 *   unauthenticated requests (currently all chat requests require auth).
 * @param message - The user's chat message text.
 * @returns The structured chat response from the backend.
 * @throws Error if the backend returns a non-ok response, with the error
 *   message extracted from the response body when available.
 */
export async function sendMessage(
  token: string | null,
  message: string,
): Promise<ChatResponse> {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const idempotencyKey = generateIdempotencyKey();

  const response = await fetch(`${apiUrl}/api/v1/chat`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
  });

  if (response.ok) {
    return response.json();
  }

  let errorMessage = "Failed to send message. Please try again.";
  try {
    const errorData = await response.json();
    if (errorData.error?.message) {
      errorMessage = errorData.error.message;
    } else if (errorData.detail) {
      errorMessage = errorData.detail;
    }
  } catch {
    // Body was not JSON
  }

  throw new Error(errorMessage);
}

/**
 * Reset the current user's chat session on the backend.
 *
 * Clears the ADK InMemorySessionService so the next message starts a fresh
 * conversation context. Does not delete conversation history from Postgres.
 *
 * @param token - The JWT access token for authentication.
 */
export async function resetChat(token: string | null): Promise<void> {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  await fetch(`${apiUrl}/api/v1/chat/reset`, {
    method: "POST",
    credentials: "include",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

/**
 * Fetch the list of past conversations for the authenticated user.
 *
 * @param token - The JWT access token for authentication.
 * @returns The conversation list response from the backend.
 * @throws Error if the request fails.
 */
export async function getConversations(token: string) {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/v1/chat/conversations`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error("Failed to load conversations");
  return response.json();
}

/**
 * Fetch the full message history for a specific conversation.
 *
 * @param token - The JWT access token for authentication.
 * @param id - The UUID of the conversation to retrieve.
 * @returns The conversation detail response including all messages.
 * @throws Error if the request fails.
 */
export async function getConversationHistory(token: string, id: string) {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/v1/chat/conversations/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) throw new Error("Failed to load conversation history");
  return response.json();
}

export async function streamMessage(
  token: string | null,
  message: string,
  onChunk: (eventData: ADKSSEEvent) => void
): Promise<void> {
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const idempotencyKey = generateIdempotencyKey();

  const response = await fetch(`${apiUrl}/api/v1/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    let errorMessage = "Failed to send message.";
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.error?.message || errorMessage;
    } catch {}
    throw new Error(errorMessage);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No readable stream available");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      
      if (chunk.startsWith("data: ")) {
        try {
          const data = JSON.parse(chunk.slice(6));
          onChunk(data);
        } catch (e) {
          console.error("Error parsing SSE chunk:", e);
        }
      }
      
      boundary = buffer.indexOf("\n\n");
    }
  }
}
