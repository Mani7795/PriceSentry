"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, BellRing, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatPrice } from "@/lib/format";

interface Props {
  productId: string;
  currentCents?: number | null;
}

// "Watch price" control. Requires auth — if logged out, routes to /login.
export function WatchButton({ productId, currentCents }: Props) {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const [watching, setWatching] = useState(false);
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState("");
  const [loading, setLoading] = useState(false);

  // Check current watch state on mount (best-effort).
  useEffect(() => {
    if (!user) return;
    api.listWatchlist()
      .then((items) => setWatching(items.some((w) => w.product_id === productId)))
      .catch(() => {});
  }, [user, productId]);

  async function toggle() {
    if (!user) {
      router.push("/login");
      return;
    }
    if (watching) {
      setLoading(true);
      try {
        await api.removeFromWatchlist(productId);
        setWatching(false);
      } finally {
        setLoading(false);
      }
    } else {
      setOpen((o) => !o);
    }
  }

  async function confirm() {
    setLoading(true);
    try {
      const cents = target ? Math.round(parseFloat(target) * 100) : null;
      await api.addToWatchlist(productId, cents);
      setWatching(true);
      setOpen(false);
      setTarget("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={toggle}
        disabled={loading}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium hover:border-primary disabled:opacity-60"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : watching ? <BellRing className="w-4 h-4 text-primary" /> : <Bell className="w-4 h-4" />}
        {watching ? "Watching" : "Watch price"}
      </button>

      {open && (
        <div className="absolute z-10 mt-2 w-64 rounded-lg border border-border bg-surface p-3 shadow-lg">
          <label className="block text-xs text-muted mb-1">
            Alert me when price drops to (optional)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.01"
              min="0"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder={currentCents ? (currentCents / 100).toFixed(2) : "0.00"}
              className="w-full rounded-md border border-border bg-bg px-2 py-1.5 text-sm outline-none focus:border-primary"
            />
            <button
              onClick={confirm}
              disabled={loading}
              className="rounded-md bg-primary text-primary-fg px-3 py-1.5 text-sm disabled:opacity-60"
            >
              Save
            </button>
          </div>
          <p className="text-[11px] text-muted mt-1.5">
            Leave blank to be alerted whenever it becomes a great deal.
            {currentCents ? ` Current: ${formatPrice(currentCents)}.` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
