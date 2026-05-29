import { ArrowDown, ArrowUp, ExternalLink, Minus, Tag } from "lucide-react";
import { cn } from "@/lib/cn";
import { buildBuyUrl, formatPrice, relativeTime, retailerAbbr, retailerLabel } from "@/lib/format";
import type { CompetitorPrice } from "@/lib/types";

// Small colored chip standing in for a retailer logo (no external assets).
function RetailerChip({ competitor }: { competitor: string }) {
  const colors: Record<string, string> = {
    amazon: "bg-[#FF9900] text-black",
    petbarn: "bg-[#E55934] text-white",          // Petbarn warm red-orange
    petzoo: "bg-[#7C3AED] text-white",           // distinct violet
    vetproductsdirect: "bg-[#0D9488] text-white", // teal
    demo: "bg-slate-500 text-white",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-md text-[10px] font-bold w-7 h-7 shrink-0",
        colors[competitor] || "bg-slate-400 text-white"
      )}
      title={retailerLabel(competitor)}
    >
      {retailerAbbr(competitor)}
    </span>
  );
}

export function CompetitorPriceRow({ price }: { price: CompetitorPrice }) {
  const diff = price.price_diff_pct;
  const href = buildBuyUrl(price.url, price.competitor);

  const inner = (
    <>
      <RetailerChip competitor={price.competitor} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="font-medium">{retailerLabel(price.competitor)}</span>
          {price.is_cheapest && (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
              <Tag className="w-3 h-3" /> CHEAPEST
            </span>
          )}
          {price.in_stock === false && (
            <span className="text-[10px] text-red-500 font-medium">OUT OF STOCK</span>
          )}
        </div>
        <div className="text-[11px] text-muted">{relativeTime(price.observed_at)}</div>
      </div>
      <div className="text-right">
        <div className="font-semibold tabular-nums flex items-center justify-end gap-1">
          {formatPrice(price.price_cents, price.currency)}
          {href && <ExternalLink className="w-3 h-3 text-muted" />}
        </div>
        {diff != null && diff !== 0 && (
          <div
            className={cn(
              "text-[11px] flex items-center justify-end gap-0.5",
              diff > 0 ? "text-red-500" : "text-emerald-500"
            )}
          >
            {diff > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
            {Math.abs(diff)}%
          </div>
        )}
        {diff === 0 && <div className="text-[11px] text-muted flex items-center justify-end gap-0.5"><Minus className="w-3 h-3" /></div>}
      </div>
    </>
  );

  const className = cn(
    "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors",
    price.is_cheapest ? "bg-emerald-50 dark:bg-emerald-950/30" : "bg-bg",
    href && "hover:bg-primary/5 cursor-pointer"
  );

  // When a retailer URL exists, the row links straight to that product page.
  // rel="nofollow sponsored" is the correct attribute for affiliate/outbound links.
  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="nofollow sponsored noopener noreferrer"
        className={className}
        title={`View on ${retailerLabel(price.competitor)}`}
      >
        {inner}
      </a>
    );
  }
  return <div className={className}>{inner}</div>;
}

export function CompetitorPriceWidget({ prices }: { prices: CompetitorPrice[] }) {
  if (!prices || prices.length === 0) {
    return <div className="text-xs text-muted px-2 py-1.5">No competitor prices yet.</div>;
  }
  return (
    <div className="space-y-1">
      {prices.map((p) => (
        <CompetitorPriceRow key={p.competitor} price={p} />
      ))}
    </div>
  );
}
