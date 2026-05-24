"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Star, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, formatPrice, productGradient } from "@/lib/format";
import { SentimentBadge } from "@/components/catalog/sentiment-badge";
import { CompetitorPriceWidget } from "@/components/catalog/competitor-price-widget";
import { PriceChart } from "@/components/catalog/price-chart";
import { SentimentPanel } from "@/components/catalog/sentiment-panel";
import { AIInsightCard } from "@/components/catalog/ai-insight-card";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProductDetailPage() {
  const params = useParams<{ productId: string }>();
  const productId = params.productId;

  const { data, isLoading, error } = useQuery({
    queryKey: ["product", productId],
    queryFn: () => api.getProduct(productId),
    enabled: !!productId,
  });

  if (isLoading) {
    return (
      <div className="p-6 max-w-6xl mx-auto space-y-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 text-center text-muted">
        Product not found. <Link href="/dashboard" className="text-primary hover:underline">Back to dashboard</Link>
      </div>
    );
  }

  const { product, price_history, sentiment } = data;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
        <ArrowLeft className="w-4 h-4" /> Back to dashboard
      </Link>

      {/* Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex gap-4">
            <div
              className="w-40 h-40 rounded-xl shrink-0"
              style={{ background: productGradient(product.brand || product.title) }}
            />
            <div className="min-w-0">
              <div className="text-sm text-muted">{product.brand || "Unknown brand"}</div>
              <h1 className="text-xl font-semibold leading-tight mt-0.5">{product.title}</h1>
              <div className="flex items-center gap-3 mt-2 text-sm text-muted">
                {product.avg_rating != null && (
                  <span className="inline-flex items-center gap-1">
                    <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                    {product.avg_rating.toFixed(1)}
                  </span>
                )}
                <span>{formatNumber(product.review_count)} reviews</span>
                {product.category && <span className="capitalize">{product.category}</span>}
              </div>
              <div className="mt-3">
                <SentimentBadge score={product.avg_sentiment} size="md" showScore />
              </div>
            </div>
          </div>
        </div>

        {/* Competitor prices */}
        <div className="rounded-xl border border-border bg-surface p-4">
          <h3 className="font-semibold text-sm mb-3">Competitor pricing</h3>
          <CompetitorPriceWidget prices={product.competitors} />
          {product.min_price_cents != null && (
            <div className="mt-3 pt-3 border-t border-border text-xs text-muted">
              Range: {formatPrice(product.min_price_cents)} – {formatPrice(product.max_price_cents)}
            </div>
          )}
        </div>
      </div>

      {/* Price history chart */}
      <div className="rounded-xl border border-border bg-surface p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-primary" />
          <h3 className="font-semibold">Price history (90 days)</h3>
        </div>
        <PriceChart history={price_history} />
      </div>

      {/* AI insights */}
      <AIInsightCard productId={productId} />

      {/* Review intelligence */}
      <div className="rounded-xl border border-border bg-surface p-5">
        <h3 className="font-semibold mb-4">Review intelligence</h3>
        <SentimentPanel sentiment={sentiment} />
      </div>
    </div>
  );
}
