"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { formatNumber } from "@/lib/format";
import type { ProductSummary } from "@/lib/types";
import { SentimentBadge } from "./sentiment-badge";
import { DealBadge } from "./deal-badge";
import { ProductImage } from "./product-image";
import { CompetitorPriceWidget } from "./competitor-price-widget";

export function ProductCard({ product, index = 0 }: { product: ProductSummary; index?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.03, 0.3) }}
      whileHover={{ y: -4 }}
      className="h-full"
    >
      {/* Outer card is a div so the competitor rows (external <a> links) are not
          nested inside the internal <Link> (anchor-in-anchor is invalid HTML). */}
      <div className="group h-full flex flex-col rounded-xl border border-border bg-surface overflow-hidden hover:border-primary hover:shadow-lg transition-all duration-200">
        <Link href={`/products/${product.product_id}`} className="block">
          {/* Real product image with gradient fallback */}
          <div className="h-40 w-full relative">
            <ProductImage
              src={product.image_url}
              seed={product.brand || product.title}
              alt={product.title}
              className="h-40 w-full"
            />
            <div className="absolute top-2 left-2 flex flex-col gap-1 items-start z-10">
              <SentimentBadge score={product.avg_sentiment} />
              <DealBadge label={product.deal_label} />
            </div>
            {product.cheapest_competitor && (
              <div className="absolute bottom-2 right-2 bg-black/55 text-white text-[10px] px-2 py-0.5 rounded-full backdrop-blur z-10">
                Best: {product.cheapest_competitor}
              </div>
            )}
          </div>

          <div className="p-4 pb-2 space-y-2">
            <div>
              <div className="text-xs text-muted">{product.brand || "Unknown brand"}</div>
              <h3 className="font-medium text-sm leading-snug line-clamp-2 group-hover:text-primary">
                {product.title}
              </h3>
            </div>

            <div className="flex items-center gap-3 text-xs text-muted">
              {product.avg_rating != null && (
                <span className="inline-flex items-center gap-1">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                  {product.avg_rating.toFixed(1)}
                </span>
              )}
              <span>{formatNumber(product.review_count)} reviews</span>
              {product.category && <span className="capitalize truncate">{product.category}</span>}
            </div>
          </div>
        </Link>

        {/* Competitor prices live OUTSIDE the internal link so each row can be
            its own outbound link to the retailer's product page. */}
        <div className="px-4 pb-4 mt-auto">
          <CompetitorPriceWidget prices={product.competitors} />
        </div>
      </div>
    </motion.div>
  );
}
