"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { LogOut, Plus, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const user = useAuth((s) => s.user);

  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
  });

  async function onLogout() {
    await api.logout();
    router.replace("/login");
  }

  return (
    <aside className="w-72 shrink-0 bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-4 border-b border-border">
        <div className="text-lg font-semibold">PriceSentry</div>
        <div className="text-xs text-muted">Review intelligence</div>
      </div>

      <div className="p-3">
        <Link
          href="/chat"
          className="flex items-center justify-center gap-2 w-full rounded-md bg-primary text-primary-fg py-2 text-sm font-medium hover:opacity-90"
        >
          <Plus className="w-4 h-4" />
          New chat
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        <div className="px-2 py-1.5 text-xs uppercase tracking-wider text-muted">
          Recent
        </div>
        {conversations.length === 0 && (
          <div className="px-3 py-2 text-sm text-muted">No conversations yet.</div>
        )}
        {conversations.map((c) => {
          const href = `/chat/${c.conversation_id}`;
          const active = pathname === href;
          return (
            <Link
              key={c.conversation_id}
              href={href}
              className={cn(
                "flex items-center gap-2 rounded-md px-2.5 py-2 text-sm truncate",
                active ? "bg-bg text-text" : "text-muted hover:bg-bg hover:text-text"
              )}
              title={c.title}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate">{c.title}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-3 border-t border-border flex items-center justify-between">
        <div className="text-sm truncate">
          <div className="font-medium truncate">{user?.full_name || user?.email}</div>
          <div className="text-xs text-muted truncate">{user?.email}</div>
        </div>
        <button
          onClick={onLogout}
          className="p-2 rounded-md hover:bg-bg text-muted hover:text-text"
          title="Log out"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
