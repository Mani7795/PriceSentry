"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { LayoutDashboard, MessagesSquare, LogIn, LogOut, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "AI Assistant", icon: MessagesSquare, requiresAuth: true },
];

export function PublicNav() {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuth((s) => s.user);

  // Silent session probe so the nav reflects auth state on public pages.
  useEffect(() => {
    if (user) return;
    (async () => {
      const ok = await api.refresh();
      if (ok) {
        try {
          useAuth.getState().setUser(await api.me());
        } catch {
          /* ignore */
        }
      }
    })();
  }, [user]);

  async function onLogout() {
    await api.logout();
    router.replace("/dashboard");
  }

  return (
    <aside className="w-60 shrink-0 bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-4 border-b border-border flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary text-primary-fg grid place-items-center">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <div className="font-semibold leading-tight">PriceSentry</div>
          <div className="text-[11px] text-muted">Pet market intelligence</div>
        </div>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                active ? "bg-bg text-text font-medium" : "text-muted hover:bg-bg hover:text-text"
              )}
            >
              <Icon className="w-4 h-4" />
              {item.label}
              {item.requiresAuth && !user && (
                <span className="ml-auto text-[10px] text-muted border border-border rounded px-1">login</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-2 border-t border-border flex items-center justify-between">
        {user ? (
          <>
            <div className="px-2 text-xs truncate">
              <div className="font-medium truncate">{user.full_name || user.email}</div>
            </div>
            <div className="flex items-center">
              <ThemeToggle />
              <button onClick={onLogout} className="p-2 rounded-md text-muted hover:bg-bg hover:text-text" title="Log out">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          <>
            <Link href="/login" className="flex items-center gap-2 px-3 py-2 text-sm text-muted hover:text-text">
              <LogIn className="w-4 h-4" /> Sign in
            </Link>
            <ThemeToggle />
          </>
        )}
      </div>
    </aside>
  );
}
