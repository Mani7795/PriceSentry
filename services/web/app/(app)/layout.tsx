"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const existingUser = useAuth.getState().user;
      if (existingUser) {
        setReady(true);
        return;
      }
      const ok = await api.refresh();
      if (cancelled) return;
      if (!ok) {
        router.replace("/login");
        return;
      }
      try {
        const me = await api.me();
        useAuth.getState().setUser(me);
        setReady(true);
      } catch {
        router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-muted">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col bg-bg overflow-hidden">{children}</main>
    </div>
  );
}
