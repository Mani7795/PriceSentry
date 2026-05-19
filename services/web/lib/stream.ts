// SSE parser for the chat stream.

import type { ChatStreamEvent, Citation } from "./types";

export async function* parseSSE(response: Response): AsyncGenerator<ChatStreamEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by \n\n; events use lines like
    //   event: token
    //   data: {...}
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evt = parseEventBlock(raw);
      if (evt) yield evt;
    }
  }
}

function parseEventBlock(block: string): ChatStreamEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // comment / keepalive
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\n");
  let data: Record<string, unknown> = {};
  try {
    data = JSON.parse(dataStr);
  } catch {
    return null;
  }
  switch (event) {
    case "start":
      return { type: "start", conversation_id: String(data.conversation_id), user_message_id: String(data.user_message_id) };
    case "token":
      return { type: "token", text: String(data.text || "") };
    case "citations":
      return { type: "citations", citations: (data.citations as Citation[]) || [] };
    case "done":
      return {
        type: "done",
        conversation_id: String(data.conversation_id),
        message_id: (data.message_id as string | null) ?? null,
        model: String(data.model || ""),
        latency_ms: Number(data.latency_ms || 0),
      };
    case "error":
      return { type: "error", detail: String(data.detail || "unknown error") };
    default:
      return null;
  }
}
