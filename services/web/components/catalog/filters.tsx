"use client";

import { Search, X } from "lucide-react";
import type { CatalogFacets, CatalogQuery } from "@/lib/types";
import { cn } from "@/lib/cn";

interface Props {
  facets?: CatalogFacets;
  query: CatalogQuery;
  onChange: (patch: Partial<CatalogQuery>) => void;
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
];

export function Filters({ facets, query, onChange }: Props) {
  const hasFilters = !!(query.brand || query.category || query.pet_type || query.sentiment || query.deal || query.q);

  return (
    <div className="space-y-5">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
        <input
          value={query.q || ""}
          onChange={(e) => onChange({ q: e.target.value, page: 1 })}
          placeholder="Search products or brands…"
          className="w-full rounded-lg border border-border bg-surface pl-9 pr-3 py-2 text-sm outline-none focus:border-primary"
        />
      </div>

      {/* Sort */}
      <div>
        <label className="block text-xs uppercase tracking-wider text-muted mb-1.5">Sort</label>
        <select
          value={query.sort || "reviews"}
          onChange={(e) => onChange({ sort: e.target.value, page: 1 })}
          className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-primary"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* Deals */}
      <FacetGroup
        title="Deals"
        active={query.deal}
        options={DEALS.map((s) => ({ value: s.value, label: s.label }))}
        onPick={(v) => onChange({ deal: (query.deal === v ? undefined : (v as any)), page: 1 })}
      />

      {/* Sentiment */}
      <FacetGroup
        title="Sentiment"
        active={query.sentiment}
        options={SENTIMENTS.map((s) => ({ value: s.value, label: s.label }))}
        onPick={(v) => onChange({ sentiment: (query.sentiment === v ? undefined : (v as any)), page: 1 })}
      />

      {/* Brands */}
      {facets && facets.brands.length > 0 && (
        <FacetGroup
          title="Brand"
          active={query.brand}
          options={facets.brands.slice(0, 10).map((f) => ({ value: f.value, label: `${f.value} (${f.count})` }))}
          onPick={(v) => onChange({ brand: query.brand === v ? undefined : v, page: 1 })}
        />
      )}

      {/* Categories */}
      {facets && facets.categories.length > 0 && (
        <FacetGroup
          title="Category"
          active={query.category}
          options={facets.categories.slice(0, 10).map((f) => ({ value: f.value, label: `${f.value} (${f.count})` }))}
          onPick={(v) => onChange({ category: query.category === v ? undefined : v, page: 1 })}
        />
      )}

      {hasFilters && (
        <button
          onClick={() => onChange({ q: "", brand: undefined, category: undefined, pet_type: undefined, sentiment: undefined, deal: undefined, page: 1 })}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <X className="w-3 h-3" /> Clear all filters
        </button>
      )}
    </div>
  );
}

function FacetGroup({
  title, active, options, onPick,
}: {
  title: string;
  active?: string;
  options: { value: string; label: string }[];
  onPick: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-muted mb-1.5">{title}</label>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={o.value}
            onClick={() => onPick(o.value)}
            className={cn(
              "rounded-full px-2.5 py-1 text-xs border transition-colors capitalize",
              active === o.value
                ? "bg-primary text-primary-fg border-primary"
                : "bg-surface border-border text-muted hover:text-text hover:border-primary"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
