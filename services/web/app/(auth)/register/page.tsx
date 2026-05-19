"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.register(email, password, fullName || undefined);
      router.replace("/chat");
    } catch (err) {
      setError((err as Error).message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <h2 className="text-xl font-medium">Create account</h2>
      {error && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-sm rounded-md px-3 py-2">
          {error}
        </div>
      )}
      <div>
        <label className="block text-sm text-muted mb-1">Full name (optional)</label>
        <input
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none focus:border-primary"
          autoComplete="name"
        />
      </div>
      <div>
        <label className="block text-sm text-muted mb-1">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none focus:border-primary"
          autoComplete="email"
        />
      </div>
      <div>
        <label className="block text-sm text-muted mb-1">Password (min 8 chars)</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 outline-none focus:border-primary"
          autoComplete="new-password"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-md bg-primary text-primary-fg py-2 font-medium disabled:opacity-60"
      >
        {loading ? "Creating…" : "Create account"}
      </button>
      <p className="text-sm text-muted text-center">
        Already have an account?{" "}
        <Link href="/login" className="text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
