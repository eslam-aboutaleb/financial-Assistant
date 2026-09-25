/**
 * ChatWindow component.
 *
 * The main conversation view. Manages message state, loads conversation
 * history when viewing an archived chat, sends new messages via React Query
 * mutation, and auto-scrolls to the latest message.
 *
 * Modes of operation:
 *   - New chat (historyId is null): User can send messages, which are
 *     appended to local state on success.
 *   - Archived chat (historyId is set): The window is read-only; messages
 *     are loaded from the backend and the input area is replaced with a
 *     notice telling the user to start a new chat.
 */

import { useChatMessages } from "@/hooks/useChatMessages";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import { StopCircle, RefreshCw, ChevronDown, Shield } from "lucide-react";

interface ChatWindowProps {
  /** Callback fired when the user starts a new chat. */
  onNewChat: () => void;
  /** If set, load and display this conversation in read-only mode. */
  historyId?: string | null;
  /** Callback fired after a message is successfully sent. */
  onMessageSent?: () => void;
}

export default function ChatWindow({
  onNewChat,
  historyId,
  onMessageSent,
}: ChatWindowProps) {
  const {
    messages,
    messagesEndRef,
    scrollRef,
    showScrollButton,
    hasError,
    isReadOnly,
    chatMutation,
    scrollToBottom,
    handleScroll,
    handleSendMessage,
    handleStopGeneration,
    handleRetryLast,
  } = useChatMessages({
    onNewChat,
    historyId,
    onMessageSent,
  });

  return (
    <div
      id="chat-window"
      className="flex flex-col h-full bg-insurance-bg relative"
      data-testid="chat-window"
      aria-label="Chat window"
    >
      <div
        id="messages-container"
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto min-h-0 px-4 md:px-6 pt-6"
        data-testid="messages-container"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div
            id="empty-state"
            className="flex flex-col items-center justify-center h-full text-center px-4 animate-fade-in"
            data-testid="empty-state"
          >
            <div className="mb-8">
              <div className="w-[72px] h-[72px] rounded-2xl bg-insurance-surface border border-insurance-border flex items-center justify-center mx-auto">
                <Shield className="w-8 h-8 text-insurance-info" />
              </div>
            </div>
            <div className="space-y-2 mb-10">
              <h2 className="text-2xl font-semibold text-insurance-ink tracking-tight">
                Welcome to OmniCare
              </h2>
              <p className="text-insurance-ink-secondary max-w-sm leading-relaxed">
                Ask about coverage, claims, or start a new claim.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-3xl">
              {[
                "Check my recent claims",
                "What is covered under water damage?",
                "File a new claim",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSendMessage(suggestion)}
                  className="px-4 py-2.5 bg-insurance-surface border border-insurance-border rounded-xl text-sm font-medium text-insurance-ink-secondary hover:text-insurance-ink hover:border-insurance-info/40 hover:shadow-soft hover:-translate-y-0.5 transition-all duration-200"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div
            id="message-list"
            className="max-w-3xl mx-auto space-y-6 pb-24"
            data-testid="message-list"
          >
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onRetry={hasError ? handleRetryLast : undefined}
              />
            ))}
            {chatMutation.isPending && !isReadOnly && (
              <div
                id="loading-indicator"
                className="flex justify-start animate-fade-in"
                data-testid="loading-indicator"
                aria-label="Assistant is typing"
              >
                <div className="bg-insurance-surface border border-insurance-border rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-3 shadow-subtle">
                  <div className="w-8 h-8 rounded-full bg-insurance-info/10 flex items-center justify-center flex-shrink-0">
                    <Shield className="w-4 h-4 text-insurance-info" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 bg-insurance-ink-tertiary rounded-full animate-typing-dot [animation-delay:-0.3s]"></div>
                    <div className="w-2 h-2 bg-insurance-ink-tertiary rounded-full animate-typing-dot [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-insurance-ink-tertiary rounded-full animate-typing-dot"></div>
                  </div>
                  <span className="text-xs text-insurance-ink-secondary">
                    OmniCare is checking your policy
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {showScrollButton && (
        <button
          onClick={() => scrollToBottom()}
          className="absolute bottom-24 right-6 z-20 p-2 bg-insurance-surface border border-insurance-border rounded-full shadow-medium hover:shadow-lifted transition-all duration-200 hover:-translate-y-0.5"
          aria-label="Scroll to bottom"
        >
          <ChevronDown className="w-4 h-4 text-insurance-ink-secondary" />
        </button>
      )}

      <div
        id="input-container"
        className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-insurance-bg via-insurance-bg/95 to-transparent pt-10"
        data-testid="input-container"
      >
        {isReadOnly ? (
          <div className="text-center p-4 text-insurance-ink-secondary bg-insurance-surface border border-insurance-border rounded-xl max-w-3xl mx-auto flex items-center justify-center gap-2">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m0 0v2m0-2h2m-2 0H10m9-9a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>
              This is an archived chat. Click &quot;New Chat&quot; to start a
              new conversation.
            </span>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            <ChatInput
              onSend={handleSendMessage}
              isLoading={chatMutation.isPending}
            />
            <div className="flex items-center justify-between mt-2.5 px-1">
              <div className="text-center text-[11px] text-insurance-ink-tertiary flex-1">
                AI-generated information. Verify important coverage and claim
                details against your policy or insurer.
              </div>
              <div className="flex items-center gap-3">
                {chatMutation.isPending && (
                  <button
                    onClick={handleStopGeneration}
                    className="flex items-center gap-1.5 text-xs text-insurance-error hover:text-insurance-ink transition-colors"
                    aria-label="Stop generating"
                  >
                    <StopCircle className="w-3.5 h-3.5" />
                    <span>Stop</span>
                  </button>
                )}
                {!chatMutation.isPending && hasError && (
                  <button
                    onClick={handleRetryLast}
                    className="flex items-center gap-1.5 text-xs text-insurance-info hover:text-insurance-ink transition-colors"
                    aria-label="Retry last message"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Retry</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
