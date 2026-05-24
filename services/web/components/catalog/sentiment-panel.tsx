"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { SentimentSummary } from "@/lib/types";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/cn";
import { SentimentBadge } from "./sentiment-badge";

export function SentimentPanel({ sentiment }: { sentiment: SentimentSummary }) {
  const { aspects, top_complaints, top_praises, pct_positive, pct_negative, review_count } = sentiment;

  return (
    <div className="space-y-5">
      {/* Overall bar */}
      <div>
        <div className="flex items-center justify-between text-xs text-muted mb-1.5">
          <span>{review_count} reviews analyzed</span>
          <span>
            {formatPct(pct_positive)} positive · {formatPct(pct_negative)} negative
          </span>
        </div>
        <div className="h-2.5 w-full rounded-full overflow-hidden flex bg-slate-200 dark:bg-slate-700">
          <div className="bg-emerald-500" style={{ width: `${(pct_positive || 0) * 100}%` }} />
          <div className="bg-red-500 ml-auto" style={{ width: `${(pct_negative || 0) * 100}%` }} />
        </div>
      </div>

      {/* Praise / complaints */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-bg p-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-emerald-600 dark:text-emerald-400 mb-2">
            <ThumbsUp className="w-4 h-4" /> Customers love
          </div>
          {top_praises.length ? (
            <ul className="text-sm space-y-1 capitalize">
              {top_praises.map((p) => <li key={p}>• {p}</li>)}
            </ul>
          ) : <p className="text-xs text-muted">No clear positive themes yet.</p>}
        </div>
        <div className="rounded-lg border border-border bg-bg p-3">
          <div className="flex items-center gap-1.5 text-sm font-medium text-red-600 dark:text-red-400 mb-2">
            <ThumbsDown className="w-4 h-4" /> Customers dislike
          </div>
          {top_complaints.length ? (
            <ul className="text-sm space-y-1 capitalize">
              {top_complaints.map((c) => <li key={c}>• {c}</li>)}
            </ul>
          ) : <p className="text-xs text-muted">No clear complaints yet.</p>}
        </div>
      </div>

      {/* Aspect breakdown */}
      {aspects.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wider text-muted mb-2">Aspect breakdown</div>
          <div className="space-y-1.5">
            {aspects.map((a) => (
              <div key={a.aspect} className="flex items-center gap-3 text-sm">
                <span className="w-24 capitalize shrink-0">{a.aspect}</span>
                <div className="flex-1 h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <div
                    className={cn(
                      "h-full",
                      a.label === "positive" ? "bg-emerald-500" : a.label === "negative" ? "bg-red-500" : "bg-slate-400"
                    )}
                    style={{ width: `${Math.min(100, Math.abs(a.avg_sentiment) * 100 + 15)}%` }}
                  />
                </div>
                <span className="text-xs text-muted w-16 text-right">{a.mentions} mentions</span>
                <SentimentBadge label={a.label} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
