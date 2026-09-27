import { describe, it, expect } from "vitest";
import {
  ChatResponseSchema,
  ConversationMetaSchema,
  UserMeSchema,
} from "@/lib/validation";

describe("validation schemas", () => {
  it("ChatResponseSchema validates a valid response", () => {
    const data = {
      response: "Hello",
      sources: ["source1"],
      tool_calls: [{ name: "tool", arguments: {} }],
    };
    expect(() => ChatResponseSchema.parse(data)).not.toThrow();
  });

  it("ChatResponseSchema rejects invalid response", () => {
    expect(() => ChatResponseSchema.parse({ response: 123 })).toThrow();
  });

  it("ConversationMetaSchema validates a valid meta", () => {
    const data = {
      id: "123",
      title: "Chat",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };
    expect(() => ConversationMetaSchema.parse(data)).not.toThrow();
  });

  it("UserMeSchema validates a valid user me", () => {
    const data = { user_id: "user-123" };
    expect(() => UserMeSchema.parse(data)).not.toThrow();
  });

  it("UserMeSchema rejects invalid user me", () => {
    expect(() => UserMeSchema.parse({ user_id: 123 })).toThrow();
  });
});
