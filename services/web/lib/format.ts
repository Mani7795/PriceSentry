// Small formatting helpers.

export function formatPrice(cents: number | null | undefined, currency = "USD"): string {
  if (cents == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatPct(fraction: number | null | undefined, digits = 0): string {
  if (fraction == null) return "—";
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export function sentimentLabel(score: number | null | undefined): "positive" | "neutral" | "negative" {
  if (score == null) return "neutral";
  if (score >= 0.05) return "positive";
  if (score <= -0.05) return "negative";
  return "neutral";
}

const RETAILER_LABELS: Record<string, string> = {
  amazon: "Amazon",
  chewy: "Chewy",
  petco: "Petco",
  petsmart: "PetSmart",
  demo: "Demo",
};
export function retailerLabel(key: string): string {
  return RETAILER_LABELS[key] || key;
}

// Affiliate tags per retailer. Fill these once you're approved into each
// program (Amazon Associates, Chewy/Partnerize, Petco/PetSmart via Impact).
// Leaving them blank just returns the plain retailer URL.
const AFFILIATE_TAGS: Record<string, string> = {
  amazon: "", // e.g. "yourtag-20"  -> appended as ?tag=yourtag-20
  chewy: "",
  petco: "",
  petsmart: "",
};

// Build the outbound "buy" link. For Amazon, appends the associate tag if set.
// Other retailers typically use network deep-links; drop those in here later.
export function buildBuyUrl(url: string | null | undefined, competitor: string): string | null {
  if (!url) return null;
  const tag = AFFILIATE_TAGS[competitor];
  try {
    const u = new URL(url);
    if (competitor === "amazon" && tag) u.searchParams.set("tag", tag);
    return u.toString();
  } catch {
    return url;
  }
}

// Deterministic placeholder image (no external assets needed).
// Uses a category/brand-derived gradient seed.
export function productGradient(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360;
  const h2 = (h + 40) % 360;
  return `linear-gradient(135deg, hsl(${h} 60% 55%), hsl(${h2} 60% 45%))`;
}
