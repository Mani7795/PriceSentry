"use client";

import { cn } from "@/lib/cn";
import type { Message as MessageType, Citation } from "@/lib/types";

interface Props {
  message: Pick<MessageType, "role" | "content"> & {
    citations?: Citation[];
    streaming?: boolean;
  };
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-2xl rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap",
          isUser
            ? "bg-primary text-primary-fg rounded-br-sm"
            : "bg-surface border border-border rounded-bl-sm"
        )}
      >
        {message.content || (message.streaming ? <span className="inline-block w-2 h-4 align-middle bg-current animate-pulse" /> : null)}
        {message.streaming && message.content && (
          <span className="inline-block w-2 h-4 ml-0.5 align-middle bg-current animate-pulse" />
        )}
      </div>
    </div>
  );
}
