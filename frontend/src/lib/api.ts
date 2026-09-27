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
import {
  ChatResponseSchema,
  ConversationMetaSchema,
  ConversationDetailSchema,
  UserMeSchema,
} from "@/lib/validation";
import { z } from "zod";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getApiUrl(): string {
  return import.meta.env.VITE_API_URL || "http://localhost:8000";
}

function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

async function parseResponse<T>(
  response: Response,
  schema: (data: unknown) => T,
): Promise<T> {
  const data = await response.json();
  if (response.ok) {
    return schema(data);
  }

  let errorMessage = "Something went wrong. Please try again later.";
  let errorCode: string | undefined;

  try {
    if (data?.error?.message) {
      errorMessage = data.error.message;
    } else if (data?.detail) {
      errorMessage = data.detail;
    }
    errorCode = data?.error?.code;
  } catch {
    // Body was not JSON
  }

  if (response.status === 401) {
    errorMessage = "Session expired. Please log in again.";
    errorCode = "UNAUTHORIZED";
  }

  throw new ApiError(errorMessage, response.status, errorCode);
}

function buildAuthHeaders(token: string | null): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Send a chat message to the OmniCare backend.
 */
export async function sendMessage(
  token: string | null,
  message: string,
  signal?: AbortSignal,
  idempotencyKey?: string,
): Promise<ChatResponse> {
  const apiUrl = getApiUrl();
  const key = idempotencyKey ?? generateIdempotencyKey();

  try {
    const response = await fetch(`${apiUrl}/api/v1/chat`, {
      method: "POST",
      credentials: "include",
      headers: {
        ...buildAuthHeaders(token),
        "Idempotency-Key": key,
      },
      body: JSON.stringify({ message }),
      signal,
    });

    if (response.ok) {
      return parseResponse(response, ChatResponseSchema.parse);
    }
    throw await parseResponse(response, (d) => d);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}

/**
 * Reset the current user's chat session on the backend.
 */
export async function resetChat(token: string | null): Promise<void> {
  const apiUrl = getApiUrl();

  try {
    const response = await fetch(`${apiUrl}/api/v1/chat/reset`, {
      method: "POST",
      credentials: "include",
      headers: buildAuthHeaders(token),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new ApiError(
        data?.detail ||
          data?.error?.message ||
          "Something went wrong. Please try again later.",
        response.status,
      );
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}

/**
 * Fetch the list of past conversations for the authenticated user.
 */
export async function getConversations(token: string, signal?: AbortSignal) {
  const apiUrl = getApiUrl();

  try {
    const response = await fetch(`${apiUrl}/api/v1/chat/conversations`, {
      credentials: "include",
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });

    if (response.ok) {
      return parseResponse(response, (d) => ({
        conversations: z
          .array(ConversationMetaSchema)
          .parse((d as { conversations?: unknown }).conversations ?? []),
      }));
    }
    throw await parseResponse(response, (d) => d);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}

/**
 * Fetch the full message history for a specific conversation.
 */
export async function getConversationHistory(
  token: string,
  id: string,
  signal?: AbortSignal,
) {
  const apiUrl = getApiUrl();

  try {
    const response = await fetch(`${apiUrl}/api/v1/chat/conversations/${id}`, {
      credentials: "include",
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });

    if (response.ok) {
      return parseResponse(response, ConversationDetailSchema.parse);
    }
    throw await parseResponse(response, (d) => d);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}

/**
 * Validate the current session by calling /api/v1/auth/me.
 */
export async function getCurrentUser(
  token: string | null,
  signal?: AbortSignal,
) {
  const apiUrl = getApiUrl();

  try {
    const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
      method: "GET",
      credentials: "include",
      headers: buildAuthHeaders(token),
      signal,
    });

    if (response.status === 204) {
      return null;
    }

    if (response.ok) {
      return parseResponse(response, UserMeSchema.parse);
    }
    throw await parseResponse(response, (d) => d);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}

/**
 * Stream a chat message and emit incremental text deltas.
 */
export async function streamMessage(
  token: string | null,
  message: string,
  onChunk: (eventData: ADKSSEEvent) => void,
  signal?: AbortSignal,
  idempotencyKey?: string,
): Promise<void> {
  const apiUrl = getApiUrl();
  const key = idempotencyKey ?? generateIdempotencyKey();

  try {
    const response = await fetch(`${apiUrl}/api/v1/chat/stream`, {
      method: "POST",
      credentials: "include",
      headers: {
        ...buildAuthHeaders(token),
        "Idempotency-Key": key,
      },
      body: JSON.stringify({ message }),
      signal,
    });

    if (!response.ok) {
      throw await parseResponse(response, (d) => d);
    }

    const reader = response.body?.getReader();
    if (!reader)
      throw new ApiError("No readable stream available", 0, "NETWORK_ERROR");

    const decoder = new TextDecoder();
    let buffer = "";
    let isDone = false;

    while (!isDone) {
      const { done, value } = await reader.read();
      isDone = done;
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
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if ((error as Error).name === "AbortError") {
      throw new ApiError("Request cancelled", 0, "CANCELLED");
    }
    throw new ApiError(
      "Something went wrong. Please try again later.",
      0,
      "NETWORK_ERROR",
    );
  }
}
