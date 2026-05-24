// Typed API client. Uses fetch + the access token from the Zustand store.
// On 401, attempts a single refresh via the httpOnly cookie endpoint and retries.

import { useAuth } from "./auth";
import type {
  AIInsightResponse,
  CatalogFacets,
  CatalogQuery,
  CatalogResponse,
  Conversation,
  Message,
  ProductDetail,
  TokenResponse,
  User,
} from "./types";

const BASE = "/api/v1";

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retried = false
): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = useAuth.getState().accessToken;
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (resp.status === 401 && !retried && path !== "/auth/refresh" && path !== "/auth/login") {
    // Try refresh once
    const ok = await tryRefresh();
    if (ok) return request<T>(path, init, true);
  }

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const j = await resp.json();
      detail = j.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }

  if (resp.status === 204) return undefined as unknown as T;
  return (await resp.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const data = await request<TokenResponse>("/auth/refresh", { method: "POST" }, true);
    useAuth.getState().setAccessToken(data.access_token);
    return true;
  } catch {
    useAuth.getState().clear();
    return false;
  }
}

// ────────────────────────────── Auth ──────────────────────────────
export const api = {
  async register(email: string, password: string, full_name?: string) {
    const data = await request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    });
    useAuth.getState().setAccessToken(data.access_token);
    const me = await api.me();
    useAuth.getState().setUser(me);
    return me;
  },

  async login(email: string, password: string) {
    const data = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    useAuth.getState().setAccessToken(data.access_token);
    const me = await api.me();
    useAuth.getState().setUser(me);
    return me;
  },

  async refresh() {
    return tryRefresh();
  },

  async logout() {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } finally {
      useAuth.getState().clear();
    }
  },

  async me() {
    return request<User>("/auth/me");
  },

  // ──────────────────────── Catalog (public) ────────────────────
  async listProducts(query: CatalogQuery = {}) {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    });
    const qs = params.toString();
    return request<CatalogResponse>(`/products${qs ? `?${qs}` : ""}`);
  },

  async getFacets() {
    return request<CatalogFacets>("/products/facets");
  },

  async getProduct(productId: string) {
    return request<ProductDetail>(`/products/${productId}`);
  },

  async getProductInsights(productId: string) {
    return request<AIInsightResponse>(`/products/${productId}/insights`, { method: "POST" });
  },

  // ──────────────────────── Conversations ───────────────────────
  async listConversations() {
    return request<Conversation[]>("/conversations");
  },

  async createConversation(title?: string, brand_filter?: string) {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title, brand_filter }),
    });
  },

  async getMessages(conversationId: string) {
    return request<Message[]>(`/conversations/${conversationId}/messages`);
  },

  // ──────────────────────── Streaming chat ──────────────────────
  // Returns the raw Response so the caller can read the SSE stream.
  async chatStream(body: {
    conversation_id?: string | null;
    message: string;
    brand_filter?: string | null;
  }): Promise<Response> {
    const token = useAuth.getState().accessToken;
    const resp = await fetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new ApiError(resp.status, text || resp.statusText);
    }
    return resp;
  },
};
