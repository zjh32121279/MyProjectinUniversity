import { getData, http, postData, putData, type AnyRecord, type ApiList, type QueryParams } from "@common/api/http";
import type { AdminUser } from "@common/auth/types";

export type KpiValue = {
  value: number;
  delta?: number;
};

export type GovernanceOverview = {
  updated_at?: string;
  kpis: {
    totalBooks: KpiValue;
    totalCopies: KpiValue;
    readersTotal: KpiValue;
    currentBorrowed: KpiValue;
    todayBorrow: KpiValue;
    todayReturn: KpiValue;
    reservationCount: KpiValue;
    overdueCount: KpiValue;
    auditEventsToday: KpiValue;
    aiRuleEnabledRate: KpiValue;
  };
  borrowReturnTrend: Array<{ date: string; borrow: number; return: number }>;
  copyStatusDistribution: Array<{ key: string; label: string; value: number }>;
  hotBooks: Array<{ rank: number; book_id?: number; title: string; author?: string; publisher?: string; cover_url?: string; borrow_count: number; reservation_count?: number }>;
  readerActivity: { total: number; active: number; active_ratio: number; today_active: number; today_new: number };
  systemActivities: Array<{ id: string; kind: string; title: string; actor: string; result: string; created_at: string }>;
  systemHealth: { status: string; score: number; services: Array<{ key: string; label: string; status: string; text: string }> };
};

export type AdminRow = Pick<AdminUser, "admin_code" | "name" | "email" | "is_super_admin" | "status"> & {
  id?: number;
  permissions?: string[];
  permission_template?: string;
  managed_scope?: string;
  last_login_at?: string;
  last_login_ip?: string;
  failed_login_count?: number;
  created_at?: string;
  updated_at?: string;
};

export type CreateAdminPayload = {
  admin_code: string;
  name: string;
  email?: string;
  password: string;
  is_super_admin?: boolean;
  status?: string;
};

export type RuleRow = {
  id: string;
  title: string;
  description: string;
  type: string;
  rule_type: "business_rule" | "notification_rule" | "ai_rule" | "ai_tool" | "system_builtin" | string;
  category: "borrow" | "system" | "policy" | "ai" | "airule" | string;
  active: boolean;
  status: string;
  editable?: boolean;
  editable_fields?: string[];
  priority?: string;
  risk_level?: string;
  updated_at?: string;
  data: AnyRecord;
};

export type RuleList = ApiList<RuleRow> & {
  summary?: {
    enabled: number;
    highPriority: number;
    pendingChanges: number;
    todayTriggers: number;
  };
};

export type AuditEventRow = {
  id: number | string;
  actor_type?: string;
  actor_id?: string;
  actor?: string;
  action?: string;
  eventTypeLabel?: string;
  target_table?: string;
  target_id?: string | number;
  targetLabel?: string;
  result?: string;
  resultLabel?: string;
  ip_address?: string;
  user_agent?: string;
  request_id?: string | number;
  detail?: AnyRecord;
  created_at?: string;
};

export type AuditExportResult = {
  job: {
    export_code: string;
    export_type: string;
    template_name: string;
    status: string;
    file_path?: string;
    created_at?: string;
  };
  row_count: number;
};

export const superAdminApi = {
  governanceOverview: () => getData<GovernanceOverview>("/super-admin/overview"),

  adminList: (params?: QueryParams) => getData<ApiList<AdminRow>>("/super-admin/admins", params),
  createAdmin: (body: CreateAdminPayload) => postData<AdminRow>("/super-admin/admins", body),
  updateAdmin: (adminCode: string, body: { name?: string; email?: string; is_super_admin?: boolean; status?: string }) =>
    putData<AdminRow>(`/super-admin/admins/${encodeURIComponent(adminCode)}`, body),
  setAdminStatus: (adminCode: string, status: string) =>
    postData<AdminRow>(`/super-admin/admins/${encodeURIComponent(adminCode)}/status`, { status }),
  resetAdminPassword: (adminCode: string, password: string) =>
    postData<AdminRow>(`/super-admin/admins/${encodeURIComponent(adminCode)}/reset-password`, { password }),
  adminLoginEvents: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/super-admin/admins/login-events", params),

  rules: (params?: QueryParams) => getData<RuleList>("/super-admin/ai-rules", params),
  createRule: (body: AnyRecord) => postData<RuleRow>("/super-admin/ai-rules", body),
  updateRule: (ruleId: string, body: AnyRecord) => putData<RuleRow>(`/super-admin/ai-rules/${encodeURIComponent(ruleId)}`, body),
  toggleRule: (ruleId: string, enabled: boolean) =>
    postData<AnyRecord>(`/super-admin/ai-rules/${encodeURIComponent(ruleId)}/toggle`, { enabled }),

  auditEvents: (params?: QueryParams) => getData<ApiList<AuditEventRow>>("/super-admin/audit-security/events", params),
  createAuditExport: (body?: AnyRecord) => postData<AuditExportResult>("/super-admin/audit-security/export", body ?? {}),
  downloadAuditExport: (exportCode: string) =>
    http.get(`/super-admin/audit-security/export-jobs/${encodeURIComponent(exportCode)}/download`, { responseType: "blob" }) as Promise<Blob>,
};
