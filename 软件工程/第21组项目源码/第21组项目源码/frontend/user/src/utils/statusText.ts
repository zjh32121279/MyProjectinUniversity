const STATUS_TEXT: Record<string, string> = {
  active: "借阅中",
  overdue: "已逾期",
  returned: "已归还",
  pending: "待处理",
  waiting: "等待中",
  ready: "待取书",
  ready_for_pickup: "待取书",
  fulfilled: "已完成",
  canceled: "已取消",
  cancelled: "已取消",
  expired: "已过期",
  unread: "未读",
  read: "已读",
  sent: "已读",
  draft: "未读",
  available: "可借",
  borrowed: "借出",
  reserved: "已预约",
  maintenance: "维护中",
  hot: "热门图书",
  normal: "普通图书",
  cold: "冷门图书",
  enabled: "已开启",
  disabled: "已关闭",
};

export function statusText(status: unknown, fallback = "—") {
  if (typeof status !== "string" || !status) return fallback;
  return STATUS_TEXT[status] ?? fallback;
}

export function circulationTypeText(value: unknown, fallback = "馆藏") {
  if (typeof value !== "string" || !value.trim()) return fallback;
  const key = value.trim();
  return STATUS_TEXT[key] ?? key;
}
