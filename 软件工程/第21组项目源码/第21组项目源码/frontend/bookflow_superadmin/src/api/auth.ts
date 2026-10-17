import { getData, postData } from "@common/api/http";
import type { AdminUser, LoginResponse } from "@common/auth/types";

export function login(payload: { account: string; password: string }) {
  return postData<LoginResponse>("/auth/login", payload);
}

export function me() {
  return getData<AdminUser>("/auth/me");
}

export function logout() {
  return postData<{ logged_out: boolean }>("/auth/logout");
}
