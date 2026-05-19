"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Root entry. If we can refresh, send to /chat; else to /login.
export default function RootPage() {
  const router = useRouter();
  const user = useAuth((s) => s.user);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = await api.refresh();
      if (cancelled) return;
      if (ok) {
        try {
          const me = await api.me();
          useAuth.getState().setUser(me);
          router.replace("/chat");
        } catch {
          router.replace("/login");
        }
      } else {
        router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center text-muted">
      <span>Loading…</span>
    </div>
  );
}
