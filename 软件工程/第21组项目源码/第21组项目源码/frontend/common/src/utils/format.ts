export function formatNumber(value: unknown, fallback = "0") {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return fallback;
  return new Intl.NumberFormat("zh-CN").format(numeric);
}

export function formatDateTime(value: unknown) {
  if (!value) return "-";
  if (value instanceof Date) return value.toISOString().replace("T", " ").slice(0, 16);
  if (typeof value !== "string") return "-";
  return value.replace("T", " ").slice(0, 16);
}

export function formatErrorCode(message: string) {
  const map: Record<string, string> = {
    AUTH_INVALID_CREDENTIALS: "账号或密码不正确。",
    AUTH_INVALID_TOKEN: "登录已失效，请重新登录。",
    ADMIN_INACTIVE: "管理员账号已停用。",
    AUTH_FORBIDDEN: "当前账号无权访问该页面。",
  };
  return map[message] || message;
}
