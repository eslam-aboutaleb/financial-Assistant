export interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  result?: any;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "error";
  content: string;
  sources?: string[];
  toolCalls?: ToolCall[];
  timestamp: Date;
}

export interface ChatResponse {
  response: string;
  sources: string[];
  tool_calls: ToolCall[];
}
