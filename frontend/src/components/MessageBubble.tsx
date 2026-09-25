/**
 * MessageBubble component.
 *
 * Renders a single chat message with distinct styling for user, assistant,
 * and error messages. Assistant messages support Markdown rendering with
 * syntax highlighting, source citation badges, and tool call transparency
 * badges.
 *
 * Layout:
 *   - User messages are right-aligned with an ochre background.
 *   - Assistant messages are left-aligned with a sand background and
 *     include the bot avatar.
 *   - Error messages use a red-tinted background and error icon.
 */

import { useState } from "react";
import { Message } from "@/types/chat";
import { Bot, User, AlertCircle, Copy, Check, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import SourcesBadge from "./SourcesBadge";
import ToolCallBadge from "./ToolCallBadge";

interface MessageBubbleProps {
  /** The message to render. */
  message: Message;
  /** Callback to retry the last user message. */
  onRetry?: () => void;
}

function formatTime(date: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "numeric",
    hour12: true,
  }).format(date);
}

export default function MessageBubble({
  message,
  onRetry,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = message.role === "error";
  const [copied, setCopied] = useState(false);
  const [showToolDetails, setShowToolDetails] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      id={`message-${message.id}`}
      className={`flex w-full gap-3 ${isUser ? "justify-end" : "justify-start"} items-start message-enter`}
      data-testid={`message-${message.id}`}
      data-message-role={message.role}
    >
      {!isUser && (
        <div
          id={`avatar-${message.id}`}
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${isError ? "mt-3 bg-insurance-error/10" : "mt-3.5 bg-insurance-info/10"}`}
          data-testid={`avatar-${message.id}`}
        >
          {isError ? (
            <AlertCircle
              className="w-4 h-4 text-insurance-error"
              data-testid="error-icon"
            />
          ) : (
            <Bot
              className="w-4 h-4 text-insurance-info"
              data-testid="bot-icon"
            />
          )}
        </div>
      )}

      <div
        id={`message-content-${message.id}`}
        className={`flex flex-col ${isUser ? "items-end max-w-[78%]" : "items-start max-w-[92%]"}`}
        data-testid={`message-content-${message.id}`}
      >
        <div
          id={`message-bubble-${message.id}`}
          className={`text-[15px] leading-relaxed shadow-subtle group relative transition-colors duration-200
            ${
              isUser
                ? "px-4 py-3 bg-insurance-info text-white rounded-2xl rounded-tr-sm"
                : isError
                  ? "px-4 py-3 bg-insurance-error/10 border border-insurance-error/20 text-insurance-ink rounded-2xl rounded-bl-sm"
                  : "px-4 py-3.5 bg-insurance-surface border border-insurance-border text-insurance-ink rounded-2xl rounded-bl-sm hover:border-insurance-border-strong"
            }`}
          data-testid={`message-bubble-${message.id}`}
        >
          {isUser ? (
            <div
              id={`user-text-${message.id}`}
              className="whitespace-pre-wrap"
              data-testid={`user-text-${message.id}`}
            >
              {message.content}
            </div>
          ) : (
            <div
              id={`assistant-text-${message.id}`}
              className="prose prose-slate max-w-none prose-p:my-2 prose-pre:my-0 prose-pre:p-0 prose-code:text-insurance-ink prose-code:bg-insurance-surface-secondary prose-code:px-1 prose-code:py-0.5 prose-code:rounded"
              data-testid={`assistant-text-${message.id}`}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || "");
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={vscDarkPlus as any}
                        language={match[1]}
                        PreTag="div"
                        className="rounded-lg !my-4"
                        {...props}
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        className="bg-insurance-surface-secondary px-1.5 py-0.5 rounded text-[13px] font-mono"
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* Hover actions */}
          {!isUser && !isError && (
            <div className="absolute -top-3 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <button
                onClick={handleCopy}
                className="p-1.5 bg-insurance-surface border border-insurance-border rounded-lg shadow-soft hover:shadow-medium transition-all"
                aria-label={copied ? "Copied" : "Copy message"}
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-insurance-success" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-insurance-ink-secondary" />
                )}
              </button>
            </div>
          )}
          {isError && onRetry && (
            <div className="absolute -top-3 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
              <button
                onClick={onRetry}
                className="p-1.5 bg-insurance-surface border border-insurance-border rounded-lg shadow-soft hover:shadow-medium transition-all flex items-center gap-1"
                aria-label="Retry"
              >
                <RefreshCw className="w-3.5 h-3.5 text-insurance-ink-secondary" />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 mt-1.5 px-1 opacity-70 group-hover:opacity-100 transition-opacity duration-200 sm:opacity-0 sm:group-hover:opacity-100">
          <span className="text-[11px] text-insurance-ink-tertiary">
            {formatTime(message.timestamp)}
          </span>
          {isError && (
            <span className="text-[11px] text-insurance-error">
              Failed to send
            </span>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div
            id={`sources-container-${message.id}`}
            className="mt-2 w-full"
            data-testid={`sources-container-${message.id}`}
          >
            <SourcesBadge sources={message.sources} />
          </div>
        )}

        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 w-full">
            <button
              type="button"
              onClick={() => setShowToolDetails((prev) => !prev)}
              className="flex items-center gap-1 text-xs text-insurance-ink-secondary hover:text-insurance-ink transition-colors"
              aria-expanded={showToolDetails}
              data-testid={`tool-details-toggle-${message.id}`}
            >
              {showToolDetails ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
              <span>Tool details</span>
            </button>
            {showToolDetails && (
              <div
                id={`tool-calls-container-${message.id}`}
                className="mt-2 w-full flex flex-col gap-2"
                data-testid={`tool-calls-container-${message.id}`}
              >
                <ToolCallBadge toolCalls={message.toolCalls} />
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div
          id={`user-avatar-${message.id}`}
          className="w-8 h-8 rounded-full bg-insurance-info text-white flex items-center justify-center flex-shrink-0 mt-3 shadow-subtle"
          data-testid={`user-avatar-${message.id}`}
        >
          <User className="w-4 h-4" data-testid="user-icon" />
        </div>
      )}
    </div>
  );
}
