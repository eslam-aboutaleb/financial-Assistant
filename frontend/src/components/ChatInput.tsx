import { useRef, useEffect, KeyboardEvent, useState } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    <div className="relative flex items-end w-full bg-gray-800 border border-gray-700 rounded-2xl shadow-sm focus-within:border-gray-500 focus-within:ring-1 focus-within:ring-gray-500 p-2 transition-all">
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask about your policy or claims..."
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        className="w-full max-h-[200px] bg-transparent text-gray-100 placeholder-gray-400 resize-none outline-none py-2 px-3 overflow-y-auto disabled:opacity-50"
      />
      <button
        onClick={handleSubmit}
        disabled={isLoading || !value.trim()}
        className="mb-1 mr-1 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:bg-gray-700 disabled:text-gray-500 transition-colors flex-shrink-0"
      >
        {isLoading ? (
          <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
        ) : (
          <Send className="w-5 h-5" />
        )}
      </button>
    </div>
  );
}
