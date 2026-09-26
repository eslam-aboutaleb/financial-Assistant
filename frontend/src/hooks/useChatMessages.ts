/**
 * Custom hook for managing chat message state, auto-scroll, and sending logic.
 *
 * Encapsulates:
 * - Message list state
 * - Auto-scroll behavior
 * - Mutation for sending messages
 * - Retry logic
 * - Keyboard shortcuts
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Message } from "@/types/chat";
import { sendMessage, resetChat as apiResetChat, getConversationHistory } from "@/lib/api";
import { useMutation, useQuery } from "@tanstack/react-query";
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
  const { token } = useAuth();
  
  const [messages, setMessages] = useState<Message[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Load conversation history when viewing an archived chat.
  const {
    data: historyData,
    isLoading: isLoadingHistory,
    isError: isErrorHistory,
  } = useQuery({
    queryKey: ["conversation", historyId],
    queryFn: () => getConversationHistory(token!, historyId!),
    enabled: !!historyId && !!token,
  });

  useEffect(() => {
    if (historyData?.messages) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages(
        historyData.messages.map((m: { id?: string; role: Message["role"]; content: string; timestamp?: string; sources?: string[]; tool_calls?: Message["toolCalls"] }) => ({
          id: m.id || Date.now().toString(),
          role: m.role,
          content: m.content,
          timestamp: new Date(m.timestamp || Date.now()),
          sources: m.sources,
          toolCalls: m.tool_calls,
        })) satisfies Message[],
      );
    }
  }, [historyData]);

  // Mutation for sending new chat messages.
  const chatMutation = useMutation({
    mutationFn: (content: string) => sendMessage(token, content),
    onSuccess: (data) => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
        sources: data.sources,
        toolCalls: data.tool_calls,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setHasError(false);
      if (onMessageSent) onMessageSent();
    },
    onError: (error: Error) => {
      if (error.message.includes("Session expired") || error.message.includes("Sign in to continue")) {
        onAuthError?.();
      }

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "error",
        content: error.message || "Something went wrong. Please try again later.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setHasError(true);
    },
  });

  const isReadOnly = !!historyId;
  const isLoading = chatMutation.isPending || isLoadingHistory;

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
    if (!content.trim()) return;
    setHasError(false);

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    chatMutation.mutate(content);
  };

  const handleStopGeneration = useCallback(() => {
    chatMutation.reset();
    toast.success("Stopped generating");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatMutation]);

  const handleRetryLast = useCallback(() => {
    const lastUserMessageIndex = [...messages].reverse().findIndex((m) => m.role === "user");
    if (lastUserMessageIndex !== -1) {
      const actualIndex = messages.length - 1 - lastUserMessageIndex;
      setMessages((prev) => prev.slice(0, actualIndex + 1));
      setHasError(false);
      const lastUserMessage = messages[actualIndex];
      chatMutation.mutate(lastUserMessage.content);
    }
  }, [chatMutation, messages]);

  const handleResetChat = useCallback(async () => {
    if (!token) return;
    await apiResetChat(token);
    onNewChat();
    toast.success("Chat session reset");
  }, [onNewChat, token]);

  return {
    messages,
    setMessages,
    messagesEndRef,
    scrollRef,
    showScrollButton,
    hasError,
    isReadOnly,
    isLoading,
    chatMutation,
    scrollToBottom,
    handleScroll,
    handleSendMessage,
    handleStopGeneration,
    handleRetryLast,
    handleResetChat,
  };
}
