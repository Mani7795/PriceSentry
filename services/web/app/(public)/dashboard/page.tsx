"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import type { CatalogQuery } from "@/lib/types";
import { ProductCard } from "@/components/catalog/product-card";
import { FilterBar } from "@/components/catalog/filter-bar";
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
  const pageSize = query.page_size || 24;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="min-h-full">
      <FilterBar facets={facets} query={query} onChange={patch} total={total} />

      <div className="p-6 space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <h1 className="text-2xl font-semibold tracking-tight">Product Intelligence</h1>
          <p className="text-sm text-muted mt-1">
            Competitor pricing and review sentiment across Amazon, Chewy, Petco, and PetSmart.
          </p>
        </motion.div>

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
            {items.map((p, i) => (
              <ProductCard key={p.product_id} product={p} index={i} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              disabled={(query.page || 1) <= 1}
              onClick={() => patch({ page: (query.page || 1) - 1 })}
              className="rounded-full border border-border bg-surface px-4 py-1.5 text-sm disabled:opacity-50 hover:border-primary"
            >
              Previous
            </button>
            <span className="text-sm text-muted">
              Page {query.page || 1} of {totalPages.toLocaleString()}
            </span>
            <button
              disabled={(query.page || 1) >= totalPages}
              onClick={() => patch({ page: (query.page || 1) + 1 })}
              className="rounded-full border border-border bg-surface px-4 py-1.5 text-sm disabled:opacity-50 hover:border-primary"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
