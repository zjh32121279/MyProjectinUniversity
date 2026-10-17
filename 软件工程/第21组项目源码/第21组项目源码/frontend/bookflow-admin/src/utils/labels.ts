import {
  formatAIAction as commonFormatAIAction,
  formatAIName as commonFormatAIName,
  formatAIReason as commonFormatAIReason,
  formatAIToolName as commonFormatAIToolName,
  formatDataFieldLabel as commonFormatDataFieldLabel,
  formatDataFieldValue as commonFormatDataFieldValue,
  formatHandlerType as commonFormatHandlerType,
  formatPriority as commonFormatPriority,
  formatQueueName as commonFormatQueueName,
  formatRequestedAction as commonFormatRequestedAction,
  formatRiskLevel as commonFormatRiskLevel,
  formatServiceType as commonFormatServiceType,
  formatSourceType as commonFormatSourceType,
  formatTaskGroup as commonFormatTaskGroup,
  formatTaskTitle as commonFormatTaskTitle,
  formatTechnicalCode,
} from "@common/utils/labels";

type DisplayRecord = Record<string, unknown>;

export function formatErrorCode(code: unknown) {
  const key = String(code ?? "").trim();
  const labels: Record<string, string> = {
    AI_ENGINE_NOT_CONFIGURED: "AI 引擎暂未接入",
    AI_ENGINE_UNAVAILABLE: "AI 引擎暂不可用",
    AI_PLANNER_OUTPUT_INVALID: "AI 规划结果无效",
    AI_RUN_NOT_FOUND: "未找到 AI 运行记录",
    READER_AI_UNAVAILABLE: "读者 AI 暂不可用",
    READER_AI_TOOL_FORBIDDEN: "读者 AI 工具未授权",
    AUTH_INVALID_TOKEN: "登录状态已失效",
    AUTH_INVALID_CREDENTIALS: "账号或密码错误，请检查后重试",
    AUTH_FORBIDDEN: "权限不足",
    ADMIN_INACTIVE: "该管理员账号已被停用",
    VALIDATION_ERROR: "数据校验失败",
    COPY_STATUS_INVALID: "馆藏状态无效",
    BOOK_NOT_FOUND: "未找到图书",
    COPY_NOT_FOUND: "未找到副本",
  };
  return labels[key] ?? (key ? key.replaceAll("_", " ").toLowerCase() : "-");
}

export function formatReaderType(type: unknown) {
  const key = String(type ?? "").trim();
  const labels: Record<string, string> = {
    child: "儿童读者",
    teen: "青少年读者",
    adult: "成人读者",
    senior: "老年读者",
    institution: "机构账号",
  };
  return labels[key] ?? (key || "-");
}

export function formatCopyStatus(status: unknown) {
  const key = String(status ?? "").trim();
  const labels: Record<string, string> = {
    available: "在馆可借",
    borrowed: "已借出",
    reserved: "预约保留",
    ready_for_pickup: "待取书",
    maintenance: "暂不可借",
    unavailable: "暂不可借",
  };
  return labels[key] ?? (key || "-");
}

export function formatPriority(priority: unknown) {
  return commonFormatPriority(priority);
}

export function formatPermissionTip(permission: unknown) {
  const key = String(permission ?? "").trim();
  const labels: Record<string, string> = {
    read_only: "需超级管理员权限",
    super_admin: "超级管理员可编辑",
    "catalog:write": "需馆藏写入权限",
    "readers:write": "需读者写入权限",
    "settings:write": "需系统设置权限",
  };
  return labels[key] ?? "需更高权限";
}

export function formatSourceType(source: unknown) {
  return commonFormatSourceType(source);
}

export function formatNotificationType(type: unknown) {
  const key = String(type ?? "").trim();
  const labels: Record<string, string> = {
    system: "系统通知",
    reservation: "预约通知",
    task: "任务通知",
    admin_task: "馆务任务",
    due: "到期提醒",
    due_reminder: "到期提醒",
    overdue: "逾期提醒",
    overdue_reminder: "逾期提醒",
    ai: "AI 通知",
    general: "普通通知",
  };
  return labels[key] ?? (key || "-");
}

export function formatRiskTitle(risk: DisplayRecord | unknown) {
  const row = typeof risk === "object" && risk ? (risk as DisplayRecord) : { title: risk };
  const title = String(row.title ?? "").trim();
  const type = String(row.warning_type ?? row.type ?? "").trim();
  const labels: Record<string, string> = {
    overdue: "逾期风险",
    inventory: "馆藏异常",
    popular_stock: "热门馆藏库存预警",
    reservation: "预约保留风险",
    cold: "冷门馆藏提醒",
  };
  if (title) return title;
  return labels[type] ?? "系统生成风险";
}

export function formatNotificationTitle(notification: DisplayRecord | unknown) {
  const row = typeof notification === "object" && notification ? (notification as DisplayRecord) : { title: notification };
  const title = String(row.title ?? "").trim();
  if (title) return title;
  return formatNotificationType(row.notification_type);
}

export function formatTaskTitle(task: DisplayRecord | unknown) {
  return commonFormatTaskTitle(task);
}

export function formatSecondaryText(value: unknown, fallback = "暂无补充说明") {
  let text = String(value ?? "").trim();
  if (!text) return fallback;
  const jsonStart = text.indexOf("\n{");
  if (jsonStart >= 0) text = text.slice(0, jsonStart).trim();
  if (/^[a-z0-9_.:-]+$/i.test(text) && !/[\u4e00-\u9fff]/.test(text)) return formatTechnicalCode(text, fallback);
  return text;
}

export const formatAIAction = commonFormatAIAction;
export const formatAIName = commonFormatAIName;
export const formatAIReason = commonFormatAIReason;
export const formatAIToolName = commonFormatAIToolName;
export const formatDataFieldLabel = commonFormatDataFieldLabel;
export const formatDataFieldValue = commonFormatDataFieldValue;
export const formatHandlerType = commonFormatHandlerType;
export const formatQueueName = commonFormatQueueName;
export const formatRequestedAction = commonFormatRequestedAction;
export const formatRiskLevel = commonFormatRiskLevel;
export const formatServiceType = commonFormatServiceType;
export const formatTaskGroup = commonFormatTaskGroup;
