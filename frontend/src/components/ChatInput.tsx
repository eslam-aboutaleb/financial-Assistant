/**
 * ChatInput component.
 *
 * A self-expanding textarea with an integrated send button. Users type their
 * message here and submit via Enter (without Shift) or by clicking the send
 * button. The textarea grows up to a maximum height before scrolling, keeping
 * the input compact for short messages and spacious for longer ones.
 *
 * Props:
 *   onSend: Callback invoked with the message text when the user submits.
 *   isLoading: When true, disables input and shows a spinner on the button.
 */

import { useRef, useEffect, KeyboardEvent, useState } from "react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  autoFocus?: boolean;
  /** Callback fired when the user submits a message. */
  onSend: (message: string) => void;
  /** Whether the backend is currently processing the message. */
  isLoading: boolean;
}

export default function ChatInput({ onSend, isLoading, autoFocus }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize the textarea to fit content, up to a max height.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (value.trim() && !isLoading) {
      onSend(value);
      setValue("");
    }
  };

  return (
    <div
      id="chat-input-wrapper"
      className="relative flex items-end w-full bg-warm-surface border border-warm-border rounded-2xl shadow-soft focus-within:border-ochre-400 focus-within:ring-4 focus-within:ring-ochre-500/10 transition-all duration-200"
      data-testid="chat-input-wrapper"
    >
      <textarea
        id="chat-textarea"
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about your policy or claims..."
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        className="w-full max-h-[200px] bg-transparent text-warm-ink placeholder-warm-muted resize-none outline-none py-3 px-4 overflow-y-auto disabled:opacity-50"
        data-testid="chat-textarea"
        autoFocus={autoFocus}
        aria-label="Chat message input"
      />
      <button
        id="send-button"
        onClick={handleSubmit}
        disabled={isLoading || !value.trim()}
        className="absolute right-3 bottom-3 p-2 bg-ochre-600 text-white rounded-xl hover:bg-ochre-700 disabled:bg-sand-100 disabled:text-warm-muted transition-all duration-200 flex-shrink-0 shadow-subtle disabled:shadow-none"
        data-testid="send-button"
        aria-label="Send message"
      >
        {isLoading ? (
          <div
            id="send-loading-spinner"
            className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"
            data-testid="send-loading-spinner"
          ></div>
        ) : (
          <ArrowUp className="w-5 h-5" data-testid="send-icon" />
        )}
      </button>
    </div>
  );
}
