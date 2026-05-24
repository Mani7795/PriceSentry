import { cn } from "@/lib/cn";
import { sentimentLabel } from "@/lib/format";

interface Props {
  score?: number | null;
  label?: "positive" | "neutral" | "negative";
  size?: "sm" | "md";
  showScore?: boolean;
}

export function SentimentBadge({ score, label, size = "sm", showScore = false }: Props) {
  const resolved = label || sentimentLabel(score);
  const styles: Record<string, string> = {
    positive: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
    neutral: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    negative: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
  };
  const dot: Record<string, string> = {
    positive: "bg-emerald-500",
    neutral: "bg-slate-400",
    negative: "bg-red-500",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium capitalize",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        styles[resolved]
      )}
    >
      <span className={cn("rounded-full", size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2", dot[resolved])} />
      {resolved}
      {showScore && score != null && <span className="opacity-70">({score.toFixed(2)})</span>}
    </span>
  );
}
