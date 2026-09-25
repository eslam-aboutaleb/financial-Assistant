/**
 * ChatMessageList component.
 *
 * Renders the list of messages in the chat window, including the empty state
 * when there are no messages, the loading indicator, and the scroll anchor.
 */

import { Message } from "@/types/chat";
import MessageBubble from "./MessageBubble";
import { Shield, ChevronDown } from "lucide-react";

interface ChatMessageListProps {
  messages: Message[];
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  showScrollButton: boolean;
  onScrollToBottom: () => void;
  isLoading: boolean;
  isReadOnly: boolean;
  hasError: boolean;
  onRetryLast?: () => void;
}

export default function ChatMessageList({
  messages,
  messagesEndRef,
  showScrollButton,
  onScrollToBottom,
  isLoading,
  isReadOnly,
  hasError,
  onRetryLast,
}: ChatMessageListProps) {
  return (
    <>
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
                onClick={() => onRetryLast && onRetryLast()}
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
              onRetry={hasError ? onRetryLast : undefined}
            />
          ))}
          {isLoading && !isReadOnly && (
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

      {showScrollButton && (
        <button
          onClick={onScrollToBottom}
          className="absolute bottom-24 right-6 z-20 p-2 bg-insurance-surface border border-insurance-border rounded-full shadow-medium hover:shadow-lifted transition-all duration-200 hover:-translate-y-0.5"
          aria-label="Scroll to bottom"
        >
          <ChevronDown className="w-4 h-4 text-insurance-ink-secondary" />
        </button>
      )}
    </>
  );
}
