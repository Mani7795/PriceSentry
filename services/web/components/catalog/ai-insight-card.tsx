"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles, Quote, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AIInsightResponse } from "@/lib/types";

export function AIInsightCard({ productId }: { productId: string }) {
  const [data, setData] = useState<AIInsightResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.getProductInsights(productId),
    onSuccess: (res) => setData(res),
  });

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary grid place-items-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <h3 className="font-semibold">AI Insights</h3>
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-fg px-3 py-1.5 text-sm font-medium disabled:opacity-60"
        >
          {mutation.isPending ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
          ) : data ? "Regenerate" : "Generate insights"}
        </button>
      </div>

      {!data && !mutation.isPending && (
        <p className="text-sm text-muted">
          Generate an AI summary of what customers like, dislike, and the competitive risks —
          grounded in this product's reviews with citations.
        </p>
      )}

      {mutation.isError && (
        <p className="text-sm text-red-500">Failed to generate insights. Is the AI provider running?</p>
      )}

      {data && (
        <div className="space-y-4">
          <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:font-semibold prose-p:my-1 prose-ul:my-1">
            <Markdown remarkPlugins={[remarkGfm]}>{data.summary}</Markdown>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted">
            <span>Model: {data.model}</span>
            <span>·</span>
            <span>{data.retrieved} reviews retrieved</span>
          </div>

          {data.citations.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wider text-muted mb-2">Sources</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {data.citations.map((c) => (
                  <div key={c.review_id} className="rounded-lg border border-border bg-bg p-2.5 text-xs">
                    <div className="flex items-center gap-1.5 text-muted mb-1">
                      <Quote className="w-3 h-3" />
                      <span className="font-mono">{c.review_id.slice(0, 8)}…</span>
                      {c.rating != null && <span>· ★ {c.rating}</span>}
                      {c.sentiment && <span>· {c.sentiment}</span>}
                    </div>
                    <p className="text-text leading-snug">{c.snippet}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
