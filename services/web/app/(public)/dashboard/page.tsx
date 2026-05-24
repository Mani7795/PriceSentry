"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Boxes, Star, TrendingUp, MessageSquareText } from "lucide-react";
import { api } from "@/lib/api";
import type { CatalogQuery } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import { ProductCard } from "@/components/catalog/product-card";
import { Filters } from "@/components/catalog/filters";
import { ProductCardSkeleton } from "@/components/ui/skeleton";

export default function DashboardPage() {
  const [query, setQuery] = useState<CatalogQuery>({ sort: "reviews", page: 1, page_size: 24 });

  const { data: facets } = useQuery({
    queryKey: ["facets"],
    queryFn: () => api.getFacets(),
    staleTime: 5 * 60_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["products", query],
    queryFn: () => api.listProducts(query),
    placeholderData: keepPreviousData,
  });

  function patch(p: Partial<CatalogQuery>) {
    setQuery((q) => ({ ...q, ...p }));
  }

  const total = data?.total ?? 0;
  const items = data?.items ?? [];

  return (
    <div className="flex h-full">
      {/* Filters rail */}
      <div className="w-64 shrink-0 border-r border-border bg-surface/50 p-4 overflow-y-auto hidden md:block">
        <Filters facets={facets} query={query} onChange={patch} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Product Intelligence</h1>
            <p className="text-sm text-muted mt-1">
              Competitor pricing and review sentiment across Amazon, Chewy, Petco, and PetSmart.
            </p>
          </div>

          {/* KPI cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard icon={Boxes} label="Products tracked" value={formatNumber(total)} />
            <KpiCard icon={TrendingUp} label="Retailers" value="4" />
            <KpiCard icon={MessageSquareText} label="Showing" value={formatNumber(items.length)} />
            <KpiCard icon={Star} label="Sort" value={(query.sort || "reviews").replace("_", " ")} />
          </div>

          {/* Mobile filters */}
          <div className="md:hidden">
            <Filters facets={facets} query={query} onChange={patch} />
          </div>

          {/* Grid */}
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
              {Array.from({ length: 8 }).map((_, i) => <ProductCardSkeleton key={i} />)}
            </div>
          ) : items.length === 0 ? (
            <div className="text-center text-muted py-20">
              No products match your filters. Try clearing them.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
              {items.map((p: any, i: number) => (
                <ProductCard key={p.product_id} product={p} index={i} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {total > (query.page_size || 24) && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                disabled={(query.page || 1) <= 1}
                onClick={() => patch({ page: (query.page || 1) - 1 })}
                className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-muted">
                Page {query.page || 1} of {Math.ceil(total / (query.page_size || 24))}
              </span>
              <button
                disabled={(query.page || 1) >= Math.ceil(total / (query.page_size || 24))}
                onClick={() => patch({ page: (query.page || 1) + 1 })}
                className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-muted text-xs">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <div className="text-xl font-semibold mt-1 capitalize">{value}</div>
    </div>
  );
}
