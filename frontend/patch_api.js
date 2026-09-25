const fs = require('fs');
let code = fs.readFileSync('src/lib/api.ts', 'utf8');

const newFunc = `
export async function streamMessage(
  token: string | null,
  message: string,
  onChunk: (eventData: any) => void
): Promise<void> {
  const apiUrl = process.env.VITE_API_URL || "http://localhost:8000";
  const idempotencyKey = generateIdempotencyKey();

  const response = await fetch(\`\${apiUrl}/api/v1/chat/stream\`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      ...(token ? { Authorization: \`Bearer \${token}\` } : {}),
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    let errorMessage = "Failed to send message.";
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.error?.message || errorMessage;
    } catch {}
    throw new Error(errorMessage);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No readable stream available");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    
    let boundary = buffer.indexOf("\\n\\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      
      if (chunk.startsWith("data: ")) {
        try {
          const data = JSON.parse(chunk.slice(6));
          onChunk(data);
        } catch (e) {
          console.error("Error parsing SSE chunk:", e);
        }
      }
      
      boundary = buffer.indexOf("\\n\\n");
    }
  }
}
`;

if (!code.includes("streamMessage")) {
  fs.writeFileSync('src/lib/api.ts', code + newFunc);
}
