// Shared types matching the FastAPI schemas.

export interface User {
  user_id: string;
  email: string;
  full_name?: string | null;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
}

export interface Conversation {
  conversation_id: string;
  title: string;
  brand_filter?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  review_id: string;
  rank: number;
  similarity?: number | null;
  snippet?: string | null;
  brand?: string | null;
  rating?: number | null;
}

export interface Message {
  message_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model?: string | null;
  created_at: string;
  citations?: Citation[];
}

// Events emitted by /chat/stream (SSE)
export type ChatStreamEvent =
  | { type: "start"; conversation_id: string; user_message_id: string }
  | { type: "token"; text: string }
  | { type: "citations"; citations: Citation[] }
  | {
      type: "done";
      conversation_id: string;
      message_id: string | null;
      model: string;
      latency_ms: number;
    }
  | { type: "error"; detail: string };
