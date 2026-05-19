"use client";

import { Quote, Star } from "lucide-react";
import type { Citation } from "@/lib/types";

interface Props {
  citations: Citation[];
}

export function CitationsPanel({ citations }: Props) {
  if (citations.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted px-6 text-center">
        Citations from the most recent answer will appear here.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-3">
      <div className="text-xs uppercase tracking-wider text-muted px-1">
        Sources ({citations.length})
      </div>
      {citations.map((c) => (
        <div
          key={c.review_id}
          className="bg-surface border border-border rounded-lg p-3 text-sm"
        >
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <Quote className="w-3.5 h-3.5 text-muted shrink-0" />
              <span className="text-muted truncate font-mono text-xs">
                {c.review_id.slice(0, 8)}…
              </span>
            </div>
            {typeof c.rating === "number" && (
              <span className="inline-flex items-center gap-0.5 text-xs text-muted">
                <Star className="w-3 h-3" />
                {c.rating}
              </span>
            )}
          </div>
          {c.brand && (
            <div className="text-xs text-muted mb-1.5">
              <span className="font-medium text-text">{c.brand}</span>
              {typeof c.similarity === "number" && (
                <span> · sim {c.similarity.toFixed(2)}</span>
              )}
            </div>
          )}
          <p className="text-text leading-snug">{c.snippet}</p>
        </div>
      ))}
    </div>
  );
}
