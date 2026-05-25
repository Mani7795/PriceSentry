import { Flame, TrendingDown, Minus, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";

interface Props {
  label?: string | null;
  size?: "sm" | "md";
}

const CONFIG: Record<string, { text: string; cls: string; Icon: any }> = {
  great: {
    text: "Great deal",
    cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
    Icon: Flame,
  },
  good: {
    text: "Good price",
    cls: "bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
    Icon: TrendingDown,
  },
  typical: {
    text: "Typical",
    cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    Icon: Minus,
  },
  high: {
    text: "Above average",
    cls: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
    Icon: TrendingUp,
  },
};

export function DealBadge({ label, size = "sm" }: Props) {
  if (!label || !CONFIG[label]) return null;
  const { text, cls, Icon } = CONFIG[label];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        cls
      )}
    >
      <Icon className={size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5"} />
      {text}
    </span>
  );
}
