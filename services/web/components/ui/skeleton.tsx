import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-border/60", className)} />;
}

export function ProductCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <div className="space-y-2 pt-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    </div>
  );
}
