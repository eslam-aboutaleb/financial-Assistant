"use client";

import { useState, useRef, useEffect } from "react";
import { Message } from "@/types/chat";
import { sendMessage } from "@/lib/api";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import { toast } from "react-hot-toast";

interface ChatWindowProps {
  onNewChat: () => void;
  token: string;
}

export default function ChatWindow({ onNewChat, token }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isLoading]);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    const toastId = toast.loading("Processing your request...");

    try {
      const response = await sendMessage(token, content);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      toast.success("Response received", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to send message", { id: toastId });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      id="chat-window"
      className="flex flex-col h-full bg-gray-950 relative"
      data-testid="chat-window"
      aria-label="Chat window"
    >
      <div
        id="chat-header"
        className="w-full flex justify-center items-center py-4 border-b border-gray-800 bg-gray-900 shadow-sm z-0"
        data-testid="chat-header"
      >
        <h1
          id="chat-title"
          className="text-lg font-medium text-gray-200"
          data-testid="chat-title"
        >
          OmniCare Assistant
        </h1>
      </div>

      <div
        id="messages-container"
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 md:p-6 pb-32"
        data-testid="messages-container"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <div
            id="empty-state"
            className="flex flex-col items-center justify-center h-full text-center space-y-4"
            data-testid="empty-state"
          >
            <div
              className="w-16 h-16 bg-indigo-900/50 rounded-full flex items-center justify-center text-indigo-400 mb-4"
              aria-hidden="true"
            >
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-200">
              Welcome to OmniCare Financial
            </h2>
            <p className="text-gray-400 max-w-md">
              I can help you review policy coverage, check claim statuses, and guide
              you through filing a new claim. How can I assist you today?
            </p>
          </div>
        ) : (
          <div
            id="message-list"
            className="space-y-6 max-w-3xl mx-auto"
            data-testid="message-list"
          >
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isLoading && (
              <div
                id="loading-indicator"
                className="flex justify-start animate-fade-in"
                data-testid="loading-indicator"
                aria-label="Assistant is typing"
              >
                <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center space-x-2">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div
        id="input-container"
        className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-gray-950 via-gray-950 to-transparent pt-10"
        data-testid="input-container"
      >
        <ChatInput onSend={handleSendMessage} isLoading={isLoading} />
        <div className="text-center mt-2 text-xs text-gray-500">
          OmniCare Assistant can make mistakes. Consider verifying important information.
        </div>
      </div>
    </div>
  );
}
