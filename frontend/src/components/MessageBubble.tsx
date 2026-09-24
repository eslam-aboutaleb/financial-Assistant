import { Message } from "@/types/chat";
import { Bot, User, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import SourcesBadge from "./SourcesBadge";
import ToolCallBadge from "./ToolCallBadge";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = message.role === "error";

  return (
    <div
      className={`flex w-full gap-4 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 ${isError ? "bg-red-900/50" : "bg-indigo-600"}`}
        >
          {isError ? (
            <AlertCircle className="w-5 h-5 text-red-500" />
          ) : (
            <Bot className="w-5 h-5 text-white" />
          )}
        </div>
      )}

      <div
        className={`flex flex-col max-w-[85%] ${isUser ? "items-end" : "items-start"}`}
      >
        <div
          className={`px-5 py-3.5 text-[15px] leading-relaxed
            ${
              isUser
                ? "bg-indigo-600 text-white rounded-2xl rounded-br-sm"
                : isError
                  ? "bg-red-950/30 border border-red-900 text-red-200 rounded-2xl rounded-bl-sm"
                  : "bg-gray-800 border border-gray-700 text-gray-100 rounded-2xl rounded-bl-sm"
            }`}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <div className="prose prose-invert max-w-none prose-p:my-2 prose-pre:my-0 prose-pre:p-0 prose-code:text-indigo-300">
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
                        className="rounded-md !my-4"
                        {...props}
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        className="bg-gray-700 px-1.5 py-0.5 rounded text-sm font-mono"
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
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 w-full">
            <SourcesBadge sources={message.sources} />
          </div>
        )}

        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 w-full flex flex-col gap-2">
            <ToolCallBadge toolCalls={message.toolCalls} />
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0 mt-1">
          <User className="w-5 h-5 text-white" />
        </div>
      )}
    </div>
  );
}
