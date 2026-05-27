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

// ─────────────────────────── Catalog / dashboard ───────────────────────────
export interface CompetitorPrice {
  competitor: string;
  price_cents: number | null;
  currency: string;
  in_stock: boolean | null;
  observed_at: string | null;
  price_diff_pct: number | null;
  is_cheapest: boolean;
  url: string | null;
}

export interface ProductSummary {
  product_id: string;
  brand: string | null;
  title: string;
  category: string | null;
  pet_type: string | null;
  review_count: number;
  avg_rating: number | null;
  avg_sentiment: number | null;
  pct_positive: number | null;
  competitor_count: number | null;
  min_price_cents: number | null;
  max_price_cents: number | null;
  cheapest_competitor: string | null;
  deal_label: "great" | "good" | "typical" | "high" | null;
  deal_pct_rank: number | null;
  deal_current_cents: number | null;
  image_url: string | null;
  competitors: CompetitorPrice[];
}

export interface WatchItem {
  watch_id: string;
  product_id: string;
  title: string | null;
  target_price_cents: number | null;
  current_cents: number | null;
  deal_label: string | null;
  created_at: string;
}

export interface CatalogResponse {
  total: number;
  page: number;
  page_size: number;
  items: ProductSummary[];
}

export interface FacetValue {
  value: string;
  count: number;
}
export interface CatalogFacets {
  brands: FacetValue[];
  categories: FacetValue[];
  pet_types: FacetValue[];
}

export interface PricePoint {
  observed_at: string;
  competitor: string;
  price_cents: number;
}

export interface AspectSentiment {
  aspect: string;
  mentions: number;
  avg_sentiment: number;
  label: "positive" | "neutral" | "negative";
  sample_snippet: string | null;
}

export interface SentimentSummary {
  review_count: number;
  avg_sentiment: number | null;
  pct_positive: number | null;
  pct_negative: number | null;
  aspects: AspectSentiment[];
  top_complaints: string[];
  top_praises: string[];
}

export interface ProductDetail {
  product: ProductSummary;
  price_history: PricePoint[];
  sentiment: SentimentSummary;
}

export interface AIInsightCitation {
  review_id: string;
  rating: number | null;
  sentiment: string | null;
  snippet: string;
}
export interface AIInsightResponse {
  product_id: string;
  summary: string;
  citations: AIInsightCitation[];
  model: string;
  retrieved: number;
}

export interface CatalogQuery {
  q?: string;
  brand?: string;
  category?: string;
  pet_type?: string;
  sentiment?: "positive" | "neutral" | "negative";
  deal?: "great" | "good" | "typical" | "high";
  min_price_cents?: number;
  max_price_cents?: number;
  sort?: string;
  page?: number;
  page_size?: number;
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
