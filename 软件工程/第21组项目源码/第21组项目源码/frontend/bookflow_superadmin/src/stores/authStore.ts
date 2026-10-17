import { create } from "zustand";
import { getTokenKey } from "@common/api/http";
import type { AdminUser } from "@common/auth/types";

type AuthState = {
  token: string | null;
  admin: AdminUser | null;
  setSession: (token: string, admin: AdminUser) => void;
  setAdmin: (admin: AdminUser | null) => void;
  clear: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem(getTokenKey()),
  admin: null,
  setSession: (token, admin) => {
    localStorage.setItem(getTokenKey(), token);
    set({ token, admin });
  },
  setAdmin: (admin) => set({ admin }),
  clear: () => {
    localStorage.removeItem(getTokenKey());
    set({ token: null, admin: null });
  },
}));
