"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { ChatWindow } from "@/components/chat/chat-window";

export default function ConversationPage() {
  const params = useParams<{ conversationId: string }>();
  const conversationId = params.conversationId;

  const { data, isLoading, error } = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => api.getMessages(conversationId),
    enabled: !!conversationId,
  });

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted">
        Loading conversation…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center text-red-500">
        {(error as Error).message}
      </div>
    );
  }

  return <ChatWindow conversationId={conversationId} initialMessages={data || []} />;
}
