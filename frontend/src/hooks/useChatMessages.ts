/**
 * Custom hook for managing chat message state, auto-scroll, and sending logic.
 *
 * Encapsulates:
 * - Message list state
 * - Auto-scroll behavior
 * - Streaming chat via SSE
 * - Request cancellation via AbortController
 * - Retry logic with preserved idempotency keys
 * - Keyboard shortcuts
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Message, ADKSSEEvent } from "@/types/chat";
import {
  streamMessage,
  resetChat as apiResetChat,
  getConversationHistory,
  ApiError,
} from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { toast } from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";

export function useChatMessages({
  onNewChat,
  historyId,
  onMessageSent,
  onAuthError,
}: {
  onNewChat: () => void;
  historyId?: string | null;
  onMessageSent?: () => void;
  onAuthError?: () => void;
}) {
  const { token, status } = useAuth();

  const [messages, setMessages] = useState<Message[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const idempotencyKeyRef = useRef<string>("");
  const lastSentIdempotencyKeyRef = useRef<string | null>(null);

  // Load conversation history when viewing an archived chat.
  const { data: historyData, isLoading: isLoadingHistory } = useQuery({
    queryKey: ["conversation", historyId],
    queryFn: () => getConversationHistory(token!, historyId!),
    enabled: !!historyId && !!token,
  });

  useEffect(() => {
    if (historyData?.messages) {
      // Sync conversation history from React Query into local message state.
      // This is an intentional side effect: we derive local UI state from
      // an external data source (the query result), which is exactly what
      // useEffect is designed for.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages(
        historyData.messages.map(
          (m: {
            id?: string;
            role: Message["role"];
            content: string;
            timestamp?: string;
            sources?: string[];
            tool_calls?: Message["toolCalls"];
          }) => ({
            id: m.id || Date.now().toString(),
            role: m.role,
            content: m.content,
            timestamp: new Date(m.timestamp || Date.now()),
            sources: m.sources,
            toolCalls: m.tool_calls,
          }),
        ) satisfies Message[],
      );
    }
  }, [historyData]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  useEffect(() => {
    scrollToBottom("smooth");
  }, [messages, scrollToBottom]);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setShowScrollButton(scrollHeight - scrollTop - clientHeight > 120);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        onNewChat();
      }
      if (
        e.key === "/" &&
        !e.ctrlKey &&
        !e.metaKey &&
        document.activeElement?.tagName !== "TEXTAREA" &&
        document.activeElement?.tagName !== "INPUT"
      ) {
        e.preventDefault();
        const textarea = document.getElementById("chat-textarea");
        if (textarea) (textarea as HTMLTextAreaElement).focus();
      }
      if (e.key === "Escape") {
        const sidebarOverlay = document.getElementById("sidebar-overlay");
        if (sidebarOverlay) sidebarOverlay.click();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNewChat]);

  const handleSendMessage = (content: string) => {
    if (!content.trim() || status !== "authenticated") return;
    setHasError(false);

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    const assistantId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentIdempotencyKey = `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
    idempotencyKeyRef.current = currentIdempotencyKey;
    lastSentIdempotencyKeyRef.current = currentIdempotencyKey;
    setIsStreaming(true);

    streamMessage(
      token,
      content,
      (eventData) => {
        if (eventData.type === "text_delta") {
          const text =
            typeof eventData.content === "string" ? eventData.content : "";
          if (text) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + text } : m,
              ),
            );
          }
        } else if (eventData.type === "response_complete") {
          const sources = Array.isArray(eventData.sources)
            ? eventData.sources.filter(Boolean)
            : [];
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, sources } : m)),
          );
        }
      },
      controller.signal,
      currentIdempotencyKey,
    )
      .then(() => {
        setIsStreaming(false);
        setHasError(false);
        if (onMessageSent) onMessageSent();
      })
      .catch((error) => {
        setIsStreaming(false);
        if (error instanceof ApiError && error.code === "CANCELLED") return;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, role: "error" as const, content: error.message }
              : m,
          ),
        );
        setHasError(true);
        if (error instanceof ApiError && error.status === 401) {
          onAuthError?.();
        }
      })
      .finally(() => {
        abortControllerRef.current = null;
      });
  };

  const handleStopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    toast.success("Stopped generating");
  }, []);

  const handleRetryLast = useCallback(() => {
    const lastUserMessageIndex = [...messages]
      .reverse()
      .findIndex((m) => m.role === "user");
    if (lastUserMessageIndex !== -1) {
      const actualIndex = messages.length - 1 - lastUserMessageIndex;
      setMessages((prev) => prev.slice(0, actualIndex + 1));
      setHasError(false);
      const lastUserMessage = messages[actualIndex];
      const retryIdempotencyKey =
        lastSentIdempotencyKeyRef.current ??
        `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
      idempotencyKeyRef.current = retryIdempotencyKey;

      const assistantId = (Date.now() + 1).toString();
      const assistantMessage: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      streamMessage(
        token,
        lastUserMessage.content,
        (eventData) => {
          if (eventData.type === "text_delta") {
            const text =
              typeof eventData.content === "string" ? eventData.content : "";
            if (text) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + text }
                    : m,
                ),
              );
            }
          } else if (eventData.type === "response_complete") {
            const sources = Array.isArray(eventData.sources)
              ? eventData.sources.filter(Boolean)
              : [];
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, sources } : m)),
            );
          }
        },
        controller.signal,
        retryIdempotencyKey,
      )
        .then(() => {
          setHasError(false);
          if (onMessageSent) onMessageSent();
        })
        .catch((error) => {
          if (error instanceof ApiError && error.code === "CANCELLED") return;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, role: "error" as const, content: error.message }
                : m,
            ),
          );
          setHasError(true);
          if (error instanceof ApiError && error.status === 401) {
            onAuthError?.();
          }
        })
        .finally(() => {
          abortControllerRef.current = null;
        });
    }
  }, [messages, token, onMessageSent]);

  const handleResetChat = useCallback(async () => {
    if (!token) return;
    await apiResetChat(token);
    onNewChat();
    toast.success("Chat session reset");
  }, [onNewChat, token]);

  const isReadOnly = !!historyId;
  const isLoading = status === "loading" || isLoadingHistory;

  return {
    messages,
    setMessages,
    messagesEndRef,
    scrollRef,
    showScrollButton,
    hasError,
    isReadOnly,
    isLoading,
    isStreaming,
    scrollToBottom,
    handleScroll,
    handleSendMessage,
    handleStopGeneration,
    handleRetryLast,
    handleResetChat,
  };
}
