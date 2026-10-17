import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  CenterModal,
  DataTable,
  Field,
  IconButton,
  Pagination,
  ResultTag,
  SearchInput,
  SelectFilter,
  type DataColumn,
} from "@/components/ui/SuperAdminUI";
import { ErrorState, SkeletonBlock } from "@/components/ui/States";
import { superAdminApi, type AuditEventRow } from "@/api/superAdmin";
import { formatDateTime, formatNumber } from "@common/utils/format";

const PAGE_SIZE = 10;

function actionLabel(row: AuditEventRow) {
  const value = String(row.action || "");
  const map: Record<string, string> = {
    scan_overdues: "逾期借阅扫描",
    admin_login_success: "管理员登录成功",
    login_success: "管理员登录成功",
    login_failed: "管理员登录失败",
    create_admin: "创建管理员",
    update_admin: "编辑管理员信息",
    set_admin_status: "调整管理员状态",
    reset_admin_password: "重置管理员密码",
    toggle_governance_rule: "启停治理规则",
    update_borrow_rule: "修改借阅规则",
    update_system_setting: "修改系统规则",
    update_circulation_policy: "修改流通策略",
    audit_export: "导出审计记录",
  };
  return row.eventTypeLabel && !/[_a-z]{3,}/.test(row.eventTypeLabel) ? row.eventTypeLabel : map[value] || "系统操作";
}

function moduleLabel(row: AuditEventRow) {
  const table = String(row.target_table || "");
  const action = String(row.action || "");
  const moduleMap: Record<string, string> = {
    loans: "借阅管理",
    reservations: "预约管理",
    admin_users: "管理员管理",
    admin_login_events: "登录认证",
    circulation_rules: "业务规则",
    system_settings: "系统规则",
    ai_capabilities: "AI 工具能力",
    ai_rules: "AI 规则",
    export_jobs: "审计导出",
  };
  if (moduleMap[table]) return moduleMap[table];
  if (table.includes("admin") || action.includes("admin")) return "管理员管理";
  if (table.includes("rule") || action.includes("rule")) return "AI 与规则";
  if (action.includes("export") || table.includes("export")) return "审计导出";
  if (action.includes("login")) return "登录认证";
  return "系统操作";
}

function actorLabel(value?: string) {
  const text = String(value || "");
  return {
    overdue_scheduler: "逾期调度器",
    system: "系统",
    admin: "管理员",
    super_admin: "超级管理员",
  }[text] || text || "-";
}

function roleLabel(value?: string) {
  return {
    system: "系统",
    admin: "管理员",
    super_admin: "超级管理员",
    reader: "读者",
  }[String(value || "")] || value || "-";
}

function targetLabel(row: AuditEventRow) {
  const raw = String(row.targetLabel || "").trim();
  const hasReadableLabel = raw && !/^[a-z_]+(\s+[A-Z0-9_-]+)?$/i.test(raw);
  if (hasReadableLabel) return raw;
  const id = row.target_id ? String(row.target_id) : "";
  const module = moduleLabel(row);
  if (module === "借阅管理") return id ? `借阅记录 ${id}` : "借阅记录";
  if (module === "管理员管理") return id ? `管理员 ${id}` : "管理员账号";
  if (module === "登录认证") return id ? `登录记录 ${id}` : "登录记录";
  if (module === "AI 与规则" || module.endsWith("规则")) return id ? `规则 ${id}` : module;
  return id ? `${module} ${id}` : module;
}

function detailKeyLabel(key: string) {
  const labels: Record<string, string> = {
    reason: "原因",
    old: "原状态",
    new: "新状态",
    before: "变更前",
    after: "变更后",
    row_count: "导出行数",
    export_type: "导出类型",
    format: "文件格式",
    rule_id: "规则编号",
    is_super_admin: "超级管理员",
    status: "状态",
    name: "姓名",
    email: "邮箱",
    role: "角色",
    admin_code: "管理员编号",
    target_entity_type: "对象类型",
    target_entity_id: "对象编号",
    action: "操作",
  };
  return labels[key] || key;
}

function detailValueLabel(key: string, value: unknown): string {
  if (value === true) return "是";
  if (value === false) return "否";
  if (value === null || value === undefined || value === "") return "-";
  const text = String(value);
  const statusMap: Record<string, string> = { active: "启用", disabled: "停用", success: "成功", failed: "失败", denied: "拒绝" };
  const exportMap: Record<string, string> = { admin_audit: "管理员审计记录", csv: "CSV 表格", json: "JSON 文件" };
  if (key === "status" || key === "old" || key === "new") return statusMap[text] || text;
  if (key === "role" || key === "actor_type") return roleLabel(text);
  if (key === "target_entity_type") return moduleLabel({ target_table: text } as AuditEventRow);
  if (key === "action") return actionLabel({ action: text } as AuditEventRow);
  if (key === "export_type" || key === "format") return exportMap[text] || text;
  return text;
}

function detailValue(key: string, value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => detailValue(key, item)).join("；") : "-";
  }
  if (value && typeof value === "object") {
    const parts = Object.entries(value as Record<string, unknown>)
      .filter(([childKey]) => childKey !== "file_hash")
      .slice(0, 8)
      .map(([childKey, childValue]) => `${detailKeyLabel(childKey)}：${detailValueLabel(childKey, childValue)}`);
    return parts.length ? parts.join("；") : "已记录";
  }
  return detailValueLabel(key, value);
}

function DetailRows({ detail }: { detail?: Record<string, unknown> }) {
  const data = detail || {};
  const entries = Object.entries(data).filter(([key]) => key !== "file_hash");
  if (!entries.length) return <div className="bf-empty-state min-h-[90px]">暂无补充明细</div>;
  return (
    <div className="mt-3 rounded-[8px] border border-[#e7eef8]">
      {entries.slice(0, 8).map(([key, value]) => (
        <div key={key} className="grid grid-cols-[112px_minmax(0,1fr)] gap-3 border-b border-[#edf3fb] px-3 py-2 last:border-b-0">
          <span className="text-[13px] font-black text-[#64718d]">{detailKeyLabel(key)}</span>
          <span className="min-w-0 break-words text-[13px] font-bold text-[#263653]">{detailValue(key, value)}</span>
        </div>
      ))}
    </div>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function AuditSecurityPage() {
  const [keyword, setKeyword] = useState("");
  const [module, setModule] = useState("");
  const [result, setResult] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<AuditEventRow | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [dateFrom, dateTo, keyword, module, result]);

  const params = useMemo(
    () => ({
      keyword: keyword.trim() || undefined,
      module: module || undefined,
      result: result || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [dateFrom, dateTo, keyword, module, offset, result],
  );

  const events = useQuery({ queryKey: ["super-admin", "audit-events", params], queryFn: () => superAdminApi.auditEvents(params) });
  const exportMutation = useMutation({
    mutationFn: async () => {
      const created = await superAdminApi.createAuditExport({
        export_type: "admin_audit",
        template_name: "管理员审计记录",
        format: "csv",
        filters: { ...params, limit: 5000, event_type: module || undefined },
      });
      const blob = await superAdminApi.downloadAuditExport(created.job.export_code);
      return { blob, code: created.job.export_code, count: created.row_count };
    },
    onSuccess: ({ blob, code, count }) => {
      downloadBlob(blob, `${code}.csv`);
      toast.success(`已导出 ${formatNumber(count)} 条审计记录`);
      events.refetch();
    },
  });

  const rows = events.data?.items ?? [];
  const total = events.data?.total ?? 0;

  const columns: DataColumn<AuditEventRow>[] = [
    { key: "time", header: "时间", width: "160px", render: (row) => formatDateTime(row.created_at) },
    { key: "actor", header: "操作者", width: "150px", render: (row) => <span className="font-black">{actorLabel(row.actor_id || row.actor)}</span> },
    { key: "role", header: "角色", width: "110px", render: (row) => roleLabel(row.actor_type) },
    { key: "module", header: "操作模块", width: "130px", render: (row) => moduleLabel(row) },
    { key: "action", header: "操作内容", render: (row) => actionLabel(row) },
    { key: "target", header: "操作对象", width: "180px", render: (row) => targetLabel(row) },
    { key: "result", header: "操作结果", width: "104px", render: (row) => <ResultTag result={row.result} /> },
    {
      key: "detail",
      header: "详情",
      width: "78px",
      render: (row) => <button className="bf-action-link" onClick={(event) => { event.stopPropagation(); setSelected(row); }} type="button">查看</button>,
    },
  ];

  if (events.isLoading) {
    return (
      <div className="bf-super-page">
        <SkeletonBlock className="h-[78px]" />
        <SkeletonBlock className="h-[560px]" />
      </div>
    );
  }
  if (events.isError || !events.data) return <ErrorState onRetry={() => events.refetch()} />;

  return (
    <div className="bf-super-page">
      <ToolbarShell
        keyword={keyword}
        setKeyword={setKeyword}
        module={module}
        setModule={setModule}
        result={result}
        setResult={setResult}
        dateFrom={dateFrom}
        setDateFrom={setDateFrom}
        dateTo={dateTo}
        setDateTo={setDateTo}
        exporting={exportMutation.isPending}
        onExport={() => exportMutation.mutate()}
      />

      <section className="bf-super-card flex min-h-0 flex-1 flex-col p-4">
        <DataTable rows={rows} columns={columns} rowKey={(row) => String(row.id)} selectedKey={selected ? String(selected.id) : undefined} onRowClick={setSelected} empty="没有符合条件的审计记录" />
        <Pagination total={total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
      </section>

      <CenterModal open={Boolean(selected)} width={620} title="操作详情" subtitle={selected ? formatDateTime(selected.created_at) : ""} onClose={() => setSelected(null)}>
        {selected ? (
          <>
            <Field label="操作者">{actorLabel(selected.actor_id || selected.actor)}</Field>
            <Field label="角色">{roleLabel(selected.actor_type)}</Field>
            <Field label="操作时间">{formatDateTime(selected.created_at)}</Field>
            <Field label="操作模块">{moduleLabel(selected)}</Field>
            <Field label="操作内容">{actionLabel(selected)}</Field>
            <Field label="操作对象">{targetLabel(selected)}</Field>
            <Field label="操作结果"><ResultTag result={selected.result} /></Field>
            <Field label="IP 地址">{selected.ip_address || "-"}</Field>
            <Field label="浏览器">{selected.user_agent || "-"}</Field>
            <Field label="请求编号">{selected.request_id || "-"}</Field>
            <div className="mt-5 text-[15px] font-black text-[#071434]">审计明细</div>
            <DetailRows detail={selected.detail} />
          </>
        ) : null}
      </CenterModal>
    </div>
  );
}

function ToolbarShell(props: {
  keyword: string;
  setKeyword: (value: string) => void;
  module: string;
  setModule: (value: string) => void;
  result: string;
  setResult: (value: string) => void;
  dateFrom: string;
  setDateFrom: (value: string) => void;
  dateTo: string;
  setDateTo: (value: string) => void;
  exporting: boolean;
  onExport: () => void;
}) {
  return (
    <div className="bf-toolbar">
      <div className="bf-toolbar__filters">
        <SelectFilter label="操作模块" value={props.module} onChange={props.setModule} options={[{ label: "全部", value: "" }, { label: "管理员管理", value: "admin" }, { label: "AI 与规则", value: "rule" }, { label: "审计导出", value: "export" }, { label: "登录认证", value: "login" }]} />
        <SelectFilter label="操作结果" value={props.result} onChange={props.setResult} options={[{ label: "全部", value: "" }, { label: "成功", value: "success" }, { label: "失败", value: "failed" }, { label: "拒绝", value: "denied" }]} />
        <label className="bf-select-filter">
          <span className="bf-filter-label">开始日期</span>
          <input className="h-[42px] rounded-[7px] border border-[#dce5f2] px-3 text-[14px] font-bold outline-none" type="date" value={props.dateFrom} onChange={(event) => props.setDateFrom(event.target.value)} />
        </label>
        <label className="bf-select-filter">
          <span className="bf-filter-label">结束日期</span>
          <input className="h-[42px] rounded-[7px] border border-[#dce5f2] px-3 text-[14px] font-bold outline-none" type="date" value={props.dateTo} onChange={(event) => props.setDateTo(event.target.value)} />
        </label>
        <SearchInput value={props.keyword} onChange={props.setKeyword} placeholder="搜索操作内容 / 对象 / IP" />
      </div>
      <div className="bf-toolbar__action">
        <IconButton icon="export" disabled={props.exporting} onClick={props.onExport}>
          {props.exporting ? "导出中..." : "导出审计记录"}
        </IconButton>
      </div>
    </div>
  );
}
