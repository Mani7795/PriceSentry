"use client";

import { ChatWindow } from "@/components/chat/chat-window";

// /chat — fresh conversation (no id yet). The first send creates one server-side
// and ChatWindow routes us to /chat/[conversationId].
export default function NewChatPage() {
  return <ChatWindow />;
}
