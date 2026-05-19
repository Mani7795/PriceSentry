"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { parseSSE } from "@/lib/stream";
import type { Citation, Message } from "@/lib/types";
import { Composer } from "./composer";
import { CitationsPanel } from "./citations-panel";
import { MessageBubble } from "./message";

interface Props {
  conversationId?: string;
  initialMessages?: Message[];
}

interface UiMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
}

export function ChatWindow({ conversationId, initialMessages = [] }: Props) {
  const router = useRouter();
  const qc = useQueryClient();

  const [messages, setMessages] = useState<UiMessage[]>(
    initialMessages.map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.content,
      citations: m.citations,
    }))
  );
  const [latestCitations, setLatestCitations] = useState<Citation[]>(() => {
    const last = [...initialMessages].reverse().find((m) => m.role === "assistant");
    return last?.citations || [];
  });
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  async function onSend(text: string) {
    setError(null);
    setMessages((m) => [
      ...m,
      { role: "user", content: text },
      { role: "assistant", content: "", streaming: true },
    ]);
    setStreaming(true);

    try {
      const resp = await api.chatStream({
        conversation_id: conversationId ?? null,
        message: text,
      });

      let newConvoId: string | null = null;
      let newCitations: Citation[] = [];

      for await (const evt of parseSSE(resp)) {
        if (evt.type === "start") {
          newConvoId = evt.conversation_id;
        } else if (evt.type === "citations") {
          newCitations = evt.citations;
          setLatestCitations(evt.citations);
          setMessages((m) =>
            m.map((msg, i) =>
              i === m.length - 1 ? { ...msg, citations: evt.citations } : msg
            )
          );
        } else if (evt.type === "token") {
          setMessages((m) =>
            m.map((msg, i) =>
              i === m.length - 1
                ? { ...msg, content: msg.content + evt.text, streaming: true }
                : msg
            )
          );
        } else if (evt.type === "done") {
          setMessages((m) =>
            m.map((msg, i) => (i === m.length - 1 ? { ...msg, streaming: false } : msg))
          );
        } else if (evt.type === "error") {
          throw new Error(evt.detail);
        }
      }

      // If we started a new convo, route to it and refresh sidebar
      if (!conversationId && newConvoId) {
        qc.invalidateQueries({ queryKey: ["conversations"] });
        router.replace(`/chat/${newConvoId}`);
      } else {
        qc.invalidateQueries({ queryKey: ["conversations"] });
      }
    } catch (err) {
      setError((err as Error).message || "Failed to get response");
      setMessages((m) =>
        m.map((msg, i) =>
          i === m.length - 1
            ? { ...msg, streaming: false, content: msg.content || "(no response)" }
            : msg
        )
      );
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-muted mt-16">
                <h2 className="text-lg font-medium text-text">Ask a question</h2>
                <p className="text-sm mt-1">
                  Answers cite the customer reviews they're grounded in.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-6 text-left">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => onSend(s)}
                      className="rounded-lg border border-border bg-surface p-3 text-sm hover:border-primary"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} />
            ))}
            {error && (
              <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-sm rounded-md p-3">
                {error}
              </div>
            )}
          </div>
        </div>
        <Composer onSend={onSend} disabled={streaming} />
      </div>

      <aside className="hidden lg:flex w-80 shrink-0 border-l border-border bg-bg flex-col">
        <CitationsPanel citations={latestCitations} />
      </aside>
    </div>
  );
}

const SUGGESTIONS = [
  "What do customers complain about most for dog food?",
  "Common praise across cat litter brands?",
  "Why do customers switch brands?",
  "How does packaging quality affect ratings?",
];
