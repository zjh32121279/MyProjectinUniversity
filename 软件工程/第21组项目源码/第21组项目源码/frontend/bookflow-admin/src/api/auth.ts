import { getData, getTokenKey, postData } from "@/api/http";
import type { AdminUser, LoginResponse } from "@/types/auth";

export function login(payload: { account: string; password: string }) {
  return postData<LoginResponse>("/auth/login", payload);
}

export function me() {
  return getData<AdminUser>("/auth/me");
}

export function refreshToken() {
  return postData<LoginResponse>("/auth/refresh");
}

export function logout() {
  return postData<{ logged_out: boolean }>("/auth/logout");
}

// Auto-refresh token every 30 minutes
let _refreshTimer: ReturnType<typeof setInterval> | null = null;
export function startAutoRefresh() {
  if (_refreshTimer) return;
  _refreshTimer = setInterval(async () => {
    try {
      const tk = getTokenKey();
      const token = localStorage.getItem(tk);
      if (token) {
        const res = await refreshToken();
        if (res.access_token) {
          localStorage.setItem(tk, res.access_token);
        }
      }
    } catch {
      // silent
    }
  }, 30 * 60 * 1000);
  // Also refresh when tab becomes visible
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshToken().catch(() => {});
    }
  });
}
