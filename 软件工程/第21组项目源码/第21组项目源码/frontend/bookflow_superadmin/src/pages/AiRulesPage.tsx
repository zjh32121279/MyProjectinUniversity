import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  CenterModal,
  ConfirmDialog,
  DataTable,
  Field,
  IconButton,
  Pagination,
  RuleTypeTag,
  SearchInput,
  SelectFilter,
  SegmentedFilter,
  StatusTag,
  Toolbar,
  type DataColumn,
} from "@/components/ui/SuperAdminUI";
import { ErrorState, SkeletonBlock } from "@/components/ui/States";
import { superAdminApi, type RuleRow } from "@/api/superAdmin";
import { formatDateTime } from "@common/utils/format";

const PAGE_SIZE = 10;

type RuleForm = Record<string, string>;

function valueOf(data: RuleRow["data"], key: string) {
  const value = data?.[key];
  return value === undefined || value === null ? "" : String(value);
}

function textValue(value: unknown, fallback = "-") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function readerLabel(value?: unknown, fallback?: unknown) {
  const code = String(value ?? "").toLowerCase();
  const map: Record<string, string> = {
    adult: "成人读者",
    child: "少儿读者",
    senior: "老年读者",
    institution: "机构读者",
    teacher: "教师读者",
    student: "学生读者",
    general: "普通读者",
  };
  return map[code] || textValue(fallback, value ? String(value) : "全部读者");
}

function circulationLabel(value?: unknown, fallback?: unknown) {
  const code = String(value ?? "").toLowerCase();
  const map: Record<string, string> = {
    hot: "热门馆藏",
    cold: "冷门馆藏",
    normal: "普通馆藏",
    reference: "参考馆藏",
    rare: "特藏馆藏",
  };
  return map[code] || textValue(fallback, value ? String(value) : "全部馆藏");
}

function moduleLabel(value?: unknown, fallback?: unknown) {
  const code = String(value ?? "").toLowerCase();
  const map: Record<string, string> = {
    borrow: "借阅辅助",
    borrowing: "借阅辅助",
    circulation: "流通服务",
    recommendation: "智能推荐",
    search: "智能检索",
    catalog: "编目辅助",
    audit: "审计安全",
    notification: "通知提醒",
    reader: "读者服务",
  };
  return map[code] || textValue(fallback, value ? String(value) : "AI 服务");
}

function permissionLabel(value?: unknown, fallback?: unknown) {
  const code = String(value ?? "").toUpperCase();
  const map: Record<string, string> = {
    L1: "只读查询",
    L2: "辅助建议",
    L3: "受控执行",
    L4: "高风险操作",
    L5: "超级管理员授权",
  };
  return map[code] || textValue(fallback, value ? String(value) : "未分级");
}

function valueTypeLabel(value?: unknown) {
  const code = String(value ?? "").toLowerCase();
  return { string: "文本", number: "数字", boolean: "开关", json: "结构化配置" }[code] || textValue(value);
}

function formFromRule(row: RuleRow): RuleForm {
  if (row.category === "borrow") {
    return {
      max_borrow_count: valueOf(row.data, "max_borrow_count"),
      borrow_days: valueOf(row.data, "borrow_days"),
      max_renewals: valueOf(row.data, "max_renewals"),
    };
  }
  if (row.category === "policy") {
    return {
      hot_borrow_90d_threshold: valueOf(row.data, "hot_borrow_90d_threshold"),
      hot_reserve_90d_threshold: valueOf(row.data, "hot_reserve_90d_threshold"),
      cold_borrow_365d_threshold: valueOf(row.data, "cold_borrow_365d_threshold"),
      cold_days_since_last_borrow_threshold: valueOf(row.data, "cold_days_since_last_borrow_threshold"),
    };
  }
  return {
    setting_value: valueOf(row.data, "setting_value"),
    value_type: valueOf(row.data, "value_type") || "string",
    description: valueOf(row.data, "description"),
  };
}

function payloadFromRule(row: RuleRow, form: RuleForm) {
  const numeric = (key: string) => {
    const value = Number(form[key]);
    return Number.isFinite(value) ? value : undefined;
  };
  if (row.category === "borrow") {
    return {
      max_borrow_count: numeric("max_borrow_count"),
      borrow_days: numeric("borrow_days"),
      max_renewals: numeric("max_renewals"),
    };
  }
  if (row.category === "policy") {
    return {
      hot_borrow_90d_threshold: numeric("hot_borrow_90d_threshold"),
      hot_reserve_90d_threshold: numeric("hot_reserve_90d_threshold"),
      cold_borrow_365d_threshold: numeric("cold_borrow_365d_threshold"),
      cold_days_since_last_borrow_threshold: numeric("cold_days_since_last_borrow_threshold"),
    };
  }
  return {
    setting_value: form.setting_value ?? "",
    value_type: form.value_type || "string",
    description: form.description || "",
  };
}

function RuleConfigFields({ row }: { row: RuleRow }) {
  if (row.category === "borrow") {
    return (
      <>
        <Field label="读者类型">{readerLabel(row.data.reader_type_code, row.data.reader_type_label || row.data.reader_type_name)}</Field>
        <Field label="馆藏类型">{circulationLabel(row.data.circulation_type, row.data.circulation_type_label)}</Field>
        <Field label="借阅上限">{String(row.data.max_borrow_count ?? "-")} 本</Field>
        <Field label="借阅天数">{String(row.data.borrow_days ?? "-")} 天</Field>
        <Field label="续借次数">{String(row.data.max_renewals ?? "-")} 次</Field>
      </>
    );
  }
  if (row.category === "policy") {
    return (
      <>
        <Field label="热门借阅阈值">{String(row.data.hot_borrow_90d_threshold ?? "-")}</Field>
        <Field label="热门预约阈值">{String(row.data.hot_reserve_90d_threshold ?? "-")}</Field>
        <Field label="冷门年借阅阈值">{String(row.data.cold_borrow_365d_threshold ?? "-")}</Field>
        <Field label="冷门未借天数">{String(row.data.cold_days_since_last_borrow_threshold ?? "-")} 天</Field>
      </>
    );
  }
  if (row.category === "ai") {
    return (
      <>
        <Field label="工具名称">{textValue(row.data.display_name || row.title)}</Field>
        <Field label="权限等级">{permissionLabel(row.data.permission_level, row.data.permission_label)}</Field>
        <Field label="写入数据">{row.data.writes_db ? "是" : "否"}</Field>
        <Field label="超管授权">{row.data.requires_super_authorization ? "需要" : "不需要"}</Field>
      </>
    );
  }
  if (row.category === "airule") {
    return (
      <>
        <Field label="规则编码">{String(row.data.rule_code || "-")}</Field>
        <Field label="所属模块">{moduleLabel(row.data.module, row.data.module_label)}</Field>
        <Field label="读者范围">{readerLabel(row.data.target_reader_type, row.data.target_reader_type_label)}</Field>
        <Field label="馆藏范围">{circulationLabel(row.data.target_circulation_type, row.data.target_circulation_type_label)}</Field>
      </>
    );
  }
  return (
    <>
      <Field label="配置项">{row.title}</Field>
      <Field label="配置值">{String(row.data.setting_value ?? "-")}</Field>
      <Field label="值类型">{valueTypeLabel(row.data.value_type)}</Field>
      <Field label="说明">{textValue(row.data.description, row.description)}</Field>
    </>
  );
}

function RuleEditor({ row, form, pending, onChange, onSubmit, onClose }: { row: RuleRow | "create"; form: RuleForm; pending: boolean; onChange: (patch: RuleForm) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onClose: () => void }) {
  const create = row === "create";
  const category = create ? "system" : row.category;
  return (
    <CenterModal
      open
      width={540}
      title={create ? "新增规则" : "编辑规则参数"}
      subtitle={create ? "新增系统/通知配置项" : row.title}
      onClose={onClose}
      footer={
        <>
          <IconButton tone="secondary" onClick={onClose}>取消</IconButton>
          <IconButton icon="check" type="submit" disabled={pending} onClick={() => document.getElementById("rule-form-submit")?.click()}>
            {pending ? "保存中..." : "保存"}
          </IconButton>
        </>
      }
    >
      <form className="bf-form" onSubmit={onSubmit}>
        <button id="rule-form-submit" className="hidden" type="submit" />
        {create ? (
          <>
            <label>
              规则类型
              <select value={form.rule_type || "system_builtin"} onChange={(event) => onChange({ rule_type: event.target.value })}>
                <option value="system_builtin">系统内置</option>
                <option value="notification_rule">通知规则</option>
              </select>
            </label>
            <label>
              规则编码
              <input required value={form.setting_key || ""} onChange={(event) => onChange({ setting_key: event.target.value })} placeholder="例如：逾期提醒开关" />
            </label>
          </>
        ) : null}

        {category === "borrow" ? (
          <>
            <label>
              借阅上限（本）
              <input required type="number" min={1} value={form.max_borrow_count || ""} onChange={(event) => onChange({ max_borrow_count: event.target.value })} />
            </label>
            <label>
              借阅天数
              <input required type="number" min={1} value={form.borrow_days || ""} onChange={(event) => onChange({ borrow_days: event.target.value })} />
            </label>
            <label>
              续借次数
              <input required type="number" min={0} value={form.max_renewals || ""} onChange={(event) => onChange({ max_renewals: event.target.value })} />
            </label>
          </>
        ) : null}

        {category === "policy" ? (
          <>
            <label>
              热门借阅阈值
              <input type="number" min={0} value={form.hot_borrow_90d_threshold || ""} onChange={(event) => onChange({ hot_borrow_90d_threshold: event.target.value })} />
            </label>
            <label>
              热门预约阈值
              <input type="number" min={0} value={form.hot_reserve_90d_threshold || ""} onChange={(event) => onChange({ hot_reserve_90d_threshold: event.target.value })} />
            </label>
            <label>
              冷门年借阅阈值
              <input type="number" min={0} value={form.cold_borrow_365d_threshold || ""} onChange={(event) => onChange({ cold_borrow_365d_threshold: event.target.value })} />
            </label>
            <label>
              冷门未借天数阈值
              <input type="number" min={0} value={form.cold_days_since_last_borrow_threshold || ""} onChange={(event) => onChange({ cold_days_since_last_borrow_threshold: event.target.value })} />
            </label>
          </>
        ) : null}

        {(category === "system" || create) ? (
          <>
            <label>
              值类型
              <select value={form.value_type || "string"} onChange={(event) => onChange({ value_type: event.target.value })}>
                <option value="string">文本</option>
                <option value="number">数字</option>
                <option value="boolean">开关</option>
                <option value="json">结构化配置</option>
              </select>
            </label>
            <label>
              配置值
              <input value={form.setting_value || ""} onChange={(event) => onChange({ setting_value: event.target.value })} placeholder="例如：启用" />
            </label>
            <label>
              说明
              <textarea value={form.description || ""} onChange={(event) => onChange({ description: event.target.value })} placeholder="规则说明" />
            </label>
          </>
        ) : null}
      </form>
    </CenterModal>
  );
}

export function AiRulesPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<RuleRow | null>(null);
  const [editing, setEditing] = useState<RuleRow | "create" | null>(null);
  const [form, setForm] = useState<RuleForm>({});
  const [toggleTarget, setToggleTarget] = useState<RuleRow | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [keyword, type, status]);

  useEffect(() => {
    if (editing === "create") {
      setForm({ rule_type: "system_builtin", value_type: "string", setting_value: "", description: "" });
    } else if (editing) {
      setForm(formFromRule(editing));
    }
  }, [editing]);

  const params = useMemo(
    () => ({
      keyword: keyword.trim() || undefined,
      rule_type: type || undefined,
      status: status || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [keyword, offset, status, type],
  );

  const rules = useQuery({ queryKey: ["super-admin", "rules", params], queryFn: () => superAdminApi.rules(params) });
  const invalidateRules = () => {
    queryClient.invalidateQueries({ queryKey: ["super-admin", "rules"] });
    queryClient.invalidateQueries({ queryKey: ["super-admin", "overview"] });
  };

  const createMutation = useMutation({
    mutationFn: () => superAdminApi.createRule(form),
    onSuccess: () => {
      toast.success("规则已创建");
      setEditing(null);
      invalidateRules();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ row, payload }: { row: RuleRow; payload: Record<string, unknown> }) => superAdminApi.updateRule(row.id, payload),
    onSuccess: () => {
      toast.success("规则已更新");
      setEditing(null);
      invalidateRules();
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (row: RuleRow) => superAdminApi.toggleRule(row.id, !row.active),
    onSuccess: () => {
      toast.success("规则状态已更新");
      setToggleTarget(null);
      invalidateRules();
    },
  });

  const rows = rules.data?.items ?? [];
  const total = rules.data?.total ?? 0;
  const columns: DataColumn<RuleRow>[] = [
    { key: "name", header: "规则名称", render: (row) => <div className="min-w-0"><div className="truncate font-black">{row.title}</div><div className="truncate text-[12px] text-[#64718d]">{row.description}</div></div> },
    { key: "type", header: "规则类型", width: "124px", render: (row) => <RuleTypeTag type={row.rule_type} /> },
    { key: "status", header: "状态", width: "86px", render: (row) => <StatusTag status={row.status} /> },
    { key: "editable", header: "可编辑性", width: "112px", render: (row) => <span className={row.editable ? "bf-tag bf-tag--blue" : "bf-tag bf-tag--gray"}>{row.editable ? "可编辑参数" : "只读/启停"}</span> },
    { key: "updated", header: "更新时间", width: "150px", render: (row) => formatDateTime(row.updated_at) },
    {
      key: "actions",
      header: "操作",
      width: "156px",
      render: (row) => (
        <div className="flex items-center gap-3">
          <button className="bf-action-link" onClick={(event) => { event.stopPropagation(); setSelected(row); }} type="button">查看</button>
          {row.editable ? <button className="bf-action-link" onClick={(event) => { event.stopPropagation(); setEditing(row); }} type="button">编辑</button> : null}
          {row.category !== "policy" ? (
            <button className={row.active ? "bf-action-link danger" : "bf-action-link"} onClick={(event) => { event.stopPropagation(); setToggleTarget(row); }} type="button">
              {row.active ? "停用" : "启用"}
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editing === "create") createMutation.mutate();
    else if (editing) updateMutation.mutate({ row: editing, payload: payloadFromRule(editing, form) });
  };

  if (rules.isLoading) {
    return (
      <div className="bf-super-page">
        <SkeletonBlock className="h-[78px]" />
        <SkeletonBlock className="h-[560px]" />
      </div>
    );
  }
  if (rules.isError || !rules.data) return <ErrorState onRetry={() => rules.refetch()} />;

  return (
    <div className="bf-super-page">
      <Toolbar action={<IconButton icon="plus" onClick={() => setEditing("create")}>新增规则</IconButton>}>
        <SearchInput value={keyword} onChange={setKeyword} placeholder="搜索规则名称 / 关键字" />
        <SelectFilter label="规则类型" value={type} onChange={setType} options={[{ label: "全部", value: "" }, { label: "业务规则", value: "business_rule" }, { label: "通知规则", value: "notification_rule" }, { label: "AI 规则", value: "ai_rule" }, { label: "AI 工具能力", value: "ai_tool" }, { label: "系统内置", value: "system_builtin" }]} />
        <SegmentedFilter label="状态" value={status} onChange={setStatus} options={[{ label: "全部", value: "" }, { label: "启用", value: "enabled" }, { label: "停用", value: "disabled" }]} />
      </Toolbar>

      <section className="bf-super-card flex min-h-0 flex-1 flex-col p-4">
        <DataTable rows={rows} columns={columns} rowKey={(row) => row.id} selectedKey={selected?.id} onRowClick={setSelected} empty="没有符合条件的规则" />
        <Pagination total={total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
      </section>

      <CenterModal open={Boolean(selected)} width={600} title={selected?.title || "规则详情"} subtitle={selected?.type} onClose={() => setSelected(null)}>
        {selected ? (
          <>
            <Field label="规则类型"><RuleTypeTag type={selected.rule_type} /></Field>
            <Field label="状态"><StatusTag status={selected.status} /></Field>
            <Field label="可编辑性">{selected.editable ? "可编辑参数" : "只读/启停"}</Field>
            <Field label="更新时间">{formatDateTime(selected.updated_at)}</Field>
            <RuleConfigFields row={selected} />
          </>
        ) : null}
      </CenterModal>

      {editing ? (
        <RuleEditor
          row={editing}
          form={form}
          pending={createMutation.isPending || updateMutation.isPending}
          onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          onSubmit={handleSubmit}
          onClose={() => setEditing(null)}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(toggleTarget)}
        title={toggleTarget?.active ? "停用规则" : "启用规则"}
        message={toggleTarget ? `确认${toggleTarget.active ? "停用" : "启用"}「${toggleTarget.title}」？该操作会写入审计记录。` : ""}
        confirmText={toggleTarget?.active ? "停用" : "启用"}
        tone={toggleTarget?.active ? "danger" : "primary"}
        loading={toggleMutation.isPending}
        onCancel={() => setToggleTarget(null)}
        onConfirm={() => toggleTarget && toggleMutation.mutate(toggleTarget)}
      />
    </div>
  );
}
