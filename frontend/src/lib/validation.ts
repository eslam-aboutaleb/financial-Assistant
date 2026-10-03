import { z } from "zod";

export const ChatResponseSchema = z.object({
  response: z.string(),
  sources: z.array(z.string()),
  tool_calls: z.array(
    z.object({
      name: z.string(),
      arguments: z.record(z.string(), z.unknown()),
      result: z.unknown().optional(),
    }),
  ),
});

export const ConversationMetaSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const ConversationDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  messages: z.array(
    z.object({
      id: z.string(),
      role: z.enum(["user", "assistant", "error"]),
      content: z.string(),
      timestamp: z.string(),
      sources: z.array(z.string()).optional(),
      tool_calls: z
        .array(
          z.object({
            name: z.string(),
            arguments: z.record(z.string(), z.unknown()),
            result: z.unknown().optional(),
          }),
        )
        .optional(),
    }),
  ),
});

export const UserMeSchema = z.object({
  user_id: z.string(),
});
