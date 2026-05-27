"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Search, X } from "lucide-react";
import type { CatalogFacets, CatalogQuery } from "@/lib/types";
import { Dropdown } from "@/components/ui/dropdown";

interface Props {
  facets?: CatalogFacets;
  query: CatalogQuery;
  onChange: (patch: Partial<CatalogQuery>) => void;
  total?: number;
}

const SORTS = [
  { value: "reviews", label: "Most reviewed" },
  { value: "rating", label: "Highest rated" },
  { value: "sentiment", label: "Best sentiment" },
  { value: "deals", label: "Best deals" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];
const SENTIMENTS = [
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
];
const DEALS = [
  { value: "great", label: "Great deal" },
  { value: "good", label: "Good price" },
  { value: "typical", label: "Typical" },
  { value: "high", label: "Above average" },
];

export function FilterBar({ facets, query, onChange, total }: Props) {
  // Build the list of active filters as removable chips.
  const chips: { key: keyof CatalogQuery; label: string }[] = [];
  if (query.q) chips.push({ key: "q", label: `"${query.q}"` });
  if (query.brand) chips.push({ key: "brand", label: query.brand });
  if (query.category) chips.push({ key: "category", label: query.category });
  if (query.pet_type) chips.push({ key: "pet_type", label: query.pet_type });
  if (query.sentiment) chips.push({ key: "sentiment", label: `${query.sentiment} sentiment` });
  if (query.deal) chips.push({ key: "deal", label: DEALS.find((d) => d.value === query.deal)?.label || query.deal });

  return (
    <div className="sticky top-0 z-20 bg-bg/80 backdrop-blur border-b border-border">
      <div className="p-4 space-y-3">
        {/* Row 1: search + dropdown filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              value={query.q || ""}
              onChange={(e) => onChange({ q: e.target.value, page: 1 })}
              placeholder="Search products or brands…"
              className="w-full rounded-full border border-border bg-surface pl-9 pr-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>

          <Dropdown label="Sort" value={query.sort && query.sort !== "reviews" ? query.sort : undefined}
            options={SORTS} onPick={(v) => onChange({ sort: v || "reviews", page: 1 })} />
          <Dropdown label="Deals" value={query.deal}
            options={DEALS} onPick={(v) => onChange({ deal: v as any, page: 1 })} />
          <Dropdown label="Sentiment" value={query.sentiment}
            options={SENTIMENTS} onPick={(v) => onChange({ sentiment: v as any, page: 1 })} />
          {facets && facets.brands.length > 0 && (
            <Dropdown label="Brand" value={query.brand}
              options={facets.brands.slice(0, 25).map((f) => ({ value: f.value, label: `${f.value} (${f.count})` }))}
              onPick={(v) => onChange({ brand: v, page: 1 })} />
          )}
          {facets && facets.categories.length > 0 && (
            <Dropdown label="Category" value={query.category}
              options={facets.categories.slice(0, 25).map((f) => ({ value: f.value, label: `${f.value} (${f.count})` }))}
              onPick={(v) => onChange({ category: v, page: 1 })} align="right" />
          )}
        </div>

        {/* Row 2: active filter chips + result count */}
        <div className="flex items-center justify-between gap-2 min-h-[24px]">
          <div className="flex flex-wrap items-center gap-1.5">
            <AnimatePresence>
              {chips.map((c) => (
                <motion.button
                  key={c.key}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  onClick={() => onChange({ [c.key]: c.key === "q" ? "" : undefined, page: 1 } as any)}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary px-2.5 py-1 text-xs capitalize"
                >
                  {c.label}
                  <X className="w-3 h-3" />
                </motion.button>
              ))}
            </AnimatePresence>
            {chips.length > 0 && (
              <button
                onClick={() => onChange({ q: "", brand: undefined, category: undefined, pet_type: undefined, sentiment: undefined, deal: undefined, page: 1 })}
                className="text-xs text-muted hover:text-text underline ml-1"
              >
                Clear all
              </button>
            )}
          </div>
          {total != null && (
            <div className="text-xs text-muted whitespace-nowrap">{total.toLocaleString()} products</div>
          )}
        </div>
      </div>
    </div>
  );
}
