// Lightweight auth store. Access token lives in memory (Zustand);
// refresh token lives in an httpOnly cookie set by the backend.

import { create } from "zustand";
import type { User } from "./types";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  setSession: (accessToken: string, user: User) => void;
  setUser: (user: User | null) => void;
  setAccessToken: (t: string | null) => void;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setSession: (accessToken, user) => set({ accessToken, user }),
  setUser: (user) => set({ user }),
  setAccessToken: (t) => set({ accessToken: t }),
  clear: () => set({ accessToken: null, user: null }),
}));
