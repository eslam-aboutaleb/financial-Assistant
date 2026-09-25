/**
 * TypeScript interfaces for the OmniCare chat domain.
 *
 * These types define the shape of data exchanged between the frontend and
 * backend, as well as the internal message representation used by React
 * components. They should be kept in sync with the Pydantic schemas in
 * ``backend/app/schemas/models.py``.
 */

/**
 * Represents a single tool invocation by the AI agent.
 *
 * The agent can call multiple tools in sequence; each call is recorded with
 * its name, input arguments, and optional result for transparency.
 */
export interface ToolCall {
  /** The registered name of the agent tool (e.g., "query_policy"). */
  name: string;
  /** The arguments passed to the tool by the agent. */
  arguments: Record<string, unknown>;
  /** The tool's return value, present after execution completes. */
  result?: unknown;
}

/**
 * A single message in a chat conversation.
 *
 * Messages are rendered by ``MessageBubble`` and stored in the conversation's
 * JSONB array on the backend.
 */
export interface Message {
  /** Unique identifier for this message. */
  id: string;
  /** Who sent the message: the user, the assistant, or an error marker. */
  role: "user" | "assistant" | "error";
  /** The rendered text content of the message. */
  content: string;
  /** Optional list of policy source citations attached to assistant messages. */
  sources?: string[];
  /** Optional list of tool calls made while generating this response. */
  toolCalls?: ToolCall[];
  /** ISO timestamp of when the message was created. */
  timestamp: Date;
}

/**
 * The top-level response shape returned by ``POST /api/v1/chat``.
 */
export interface ChatResponse {
  /** The agent's generated response text. */
  response: string;
  /** List of source citations (policy section strings) for RAG-grounded answers. */
  sources: string[];
  /** Trace of tool calls made during response generation. */
  tool_calls: ToolCall[];
}

/**
 * Lightweight metadata for a conversation, used in sidebar lists.
 */
export interface ConversationMeta {
  /** Unique identifier for the conversation. */
  id: string;
  /** Human-readable title, defaulting to "New Chat". */
  title: string;
  /** ISO timestamp of conversation creation. */
  created_at: string;
  /** ISO timestamp of last update. */
  updated_at: string;
}

/**
 * Full conversation detail including all messages.
 *
 * Extends ``ConversationMeta`` with the complete message history.
 */
export interface ConversationDetail extends ConversationMeta {
  /** Ordered list of messages in this conversation. */
  messages: Message[];
}

/**
 * Generic SSE event payload from the ADK streaming endpoint.
 *
 * The backend emits ADK event JSON objects; we do not need to fully type
 * every field because the frontend only forwards them to the streaming
 * consumer. If needed, expand this interface to cover specific event shapes.
 */
export interface ADKSSEEvent {
  [key: string]: unknown;
}
