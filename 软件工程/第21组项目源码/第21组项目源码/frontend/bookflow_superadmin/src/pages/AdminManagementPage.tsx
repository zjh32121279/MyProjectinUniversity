import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { AppIcon } from "@/components/icons/AppIcon";
import { ErrorState, SkeletonBlock } from "@/components/ui/States";
import {
  CenterModal,
  ConfirmDialog,
  DataTable,
  Field,
  IconButton,
  Pagination,
  ResultTag,
  RoleTag,
  SearchInput,
  SegmentedFilter,
  StatusTag,
  Toolbar,
  type DataColumn,
} from "@/components/ui/SuperAdminUI";
import { superAdminApi, type AdminRow, type CreateAdminPayload } from "@/api/superAdmin";
import { formatDateTime } from "@common/utils/format";

const PAGE_SIZE = 10;

type AdminFormState = {
  admin_code: string;
  name: string;
  email: string;
  password: string;
  is_super_admin: boolean;
  status: string;
};

function makePassword() {
  const tail = Math.random().toString(36).slice(2, 8);
  const stamp = Date.now().toString(36).slice(-4);
  return `Bf@${stamp}${tail}9A`;
}

function emptyForm(): AdminFormState {
  return {
    admin_code: "",
    name: "",
    email: "",
    password: makePassword(),
    is_super_admin: false,
    status: "active",
  };
}

function formFromRow(row: AdminRow): AdminFormState {
  return {
    admin_code: row.admin_code,
    name: row.name || "",
    email: row.email || "",
    password: "",
    is_super_admin: Boolean(row.is_super_admin),
    status: row.status || "active",
  };
}

function templateLabel(value?: string) {
  const text = String(value || "").trim();
  return {
    default: "默认权限模板",
    super_admin: "超级管理员模板",
    operator: "普通管理员模板",
    readonly: "只读模板",
  }[text] || text || "-";
}

function scopeLabel(value?: string) {
  const text = String(value || "").trim();
  return {
    all: "全部业务",
    circulation: "借阅流通",
    catalog: "图书编目",
    reader: "读者服务",
    audit: "审计安全",
  }[text] || text || "-";
}

function loginEventLabel(value?: string) {
  const text = String(value || "").trim();
  return {
    login_success: "登录成功",
    admin_login_success: "登录成功",
    login_failed: "登录失败",
    admin_login_failed: "登录失败",
    logout: "退出登录",
  }[text] || text || "登录记录";
}

function loginResult(value?: string) {
  const text = String(value || "").trim();
  if (text.includes("failed")) return "failed";
  if (text.includes("success")) return "success";
  if (text === "logout") return "success";
  return text || "success";
}

function AdminFormModal({ mode, form, pending, onChange, onClose, onSubmit }: { mode: "create" | "edit"; form: AdminFormState; pending: boolean; onChange: (patch: Partial<AdminFormState>) => void; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const isCreate = mode === "create";
  return (
    <CenterModal
      open
      width={520}
      title={isCreate ? "新增管理员" : "编辑管理员"}
      subtitle={isCreate ? "创建后会写入管理员审计记录" : form.admin_code}
      onClose={onClose}
      footer={
        <>
          <IconButton tone="secondary" onClick={onClose}>取消</IconButton>
          <IconButton icon="check" type="submit" tone="primary" disabled={pending} onClick={() => document.getElementById("admin-form-submit")?.click()}>
            {pending ? "保存中..." : "保存"}
          </IconButton>
        </>
      }
    >
      <form className="bf-form" onSubmit={onSubmit}>
        <button id="admin-form-submit" className="hidden" type="submit" />
        <label>
          管理员编号
          <input value={form.admin_code} disabled={!isCreate} required onChange={(event) => onChange({ admin_code: event.target.value })} placeholder="A02-001" />
        </label>
        <label>
          姓名
          <input value={form.name} required onChange={(event) => onChange({ name: event.target.value })} placeholder="例如：数据管理员" />
        </label>
        <label>
          邮箱/账号
          <input value={form.email} onChange={(event) => onChange({ email: event.target.value })} type="email" placeholder="admin@bookflow.com" />
        </label>
        {isCreate ? (
          <label>
            初始密码
            <div className="grid grid-cols-[minmax(0,1fr)_88px] gap-2">
              <input value={form.password} required minLength={12} onChange={(event) => onChange({ password: event.target.value })} />
              <button className="rounded-[7px] border border-[#dce5f2] text-[13px] font-black text-[#1769f7]" type="button" onClick={() => onChange({ password: makePassword() })}>
                生成
              </button>
            </div>
            <span className="text-[12px] font-bold text-[#64718d]">至少 12 位，包含大小写字母、数字和符号。</span>
          </label>
        ) : null}
        <div className="grid grid-cols-2 gap-3">
          <label>
            角色
            <select value={form.is_super_admin ? "super_admin" : "admin"} onChange={(event) => onChange({ is_super_admin: event.target.value === "super_admin" })}>
              <option value="admin">普通管理员</option>
              <option value="super_admin">超级管理员</option>
            </select>
          </label>
          <label>
            状态
            <select value={form.status} onChange={(event) => onChange({ status: event.target.value })}>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
          </label>
        </div>
      </form>
    </CenterModal>
  );
}

export function AdminManagementPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<AdminRow | null>(null);
  const [editing, setEditing] = useState<AdminRow | "create" | null>(null);
  const [form, setForm] = useState<AdminFormState>(emptyForm());
  const [statusTarget, setStatusTarget] = useState<AdminRow | null>(null);
  const [resetTarget, setResetTarget] = useState<{ row: AdminRow; password: string } | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [keyword, role, status]);

  useEffect(() => {
    if (editing === "create") setForm(emptyForm());
    else if (editing) setForm(formFromRow(editing));
  }, [editing]);

  const params = useMemo(
    () => ({
      keyword: keyword.trim() || undefined,
      is_super_admin: role === "" ? undefined : role === "super",
      status: status || undefined,
      limit: PAGE_SIZE,
      offset,
    }),
    [keyword, offset, role, status],
  );

  const admins = useQuery({ queryKey: ["super-admin", "admins", params], queryFn: () => superAdminApi.adminList(params) });
  const selectedEvents = useQuery({
    queryKey: ["super-admin", "admin-login-events", selected?.admin_code],
    queryFn: () => superAdminApi.adminLoginEvents({ admin_code: selected?.admin_code, limit: 6 }),
    enabled: Boolean(selected?.admin_code),
  });

  const invalidateAdmins = () => {
    queryClient.invalidateQueries({ queryKey: ["super-admin", "admins"] });
    queryClient.invalidateQueries({ queryKey: ["super-admin", "overview"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: CreateAdminPayload) => superAdminApi.createAdmin(payload),
    onSuccess: () => {
      toast.success("管理员已创建");
      setEditing(null);
      invalidateAdmins();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ row, body }: { row: AdminRow; body: Partial<CreateAdminPayload> }) => superAdminApi.updateAdmin(row.admin_code, body),
    onSuccess: () => {
      toast.success("管理员已更新");
      setEditing(null);
      invalidateAdmins();
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ row, nextStatus }: { row: AdminRow; nextStatus: string }) => superAdminApi.setAdminStatus(row.admin_code, nextStatus),
    onSuccess: () => {
      toast.success("管理员状态已更新");
      setStatusTarget(null);
      invalidateAdmins();
    },
  });

  const resetMutation = useMutation({
    mutationFn: ({ row, password }: { row: AdminRow; password: string }) => superAdminApi.resetAdminPassword(row.admin_code, password),
    onSuccess: (_data, variables) => {
      toast.success(`临时密码已设置：${variables.password}`);
      setResetTarget(null);
      invalidateAdmins();
    },
  });

  const rows = admins.data?.items ?? [];
  const total = admins.data?.total ?? 0;

  const columns: DataColumn<AdminRow>[] = [
    { key: "code", header: "管理员编号", render: (row) => <span className="font-black">{row.admin_code}</span> },
    { key: "name", header: "姓名", render: (row) => row.name || "-" },
    { key: "email", header: "邮箱/账号", render: (row) => <span className="text-[#52617d]">{row.email || "-"}</span> },
    { key: "role", header: "角色", render: (row) => <RoleTag isSuperAdmin={row.is_super_admin} /> },
    { key: "status", header: "状态", render: (row) => <StatusTag status={row.status} /> },
    { key: "login", header: "最近登录", render: (row) => formatDateTime(row.last_login_at) },
    {
      key: "actions",
      header: "操作",
      render: (row) => (
        <div className="flex items-center gap-3">
          <button className="bf-action-link" type="button" onClick={(event) => { event.stopPropagation(); setSelected(row); }}>
            查看
          </button>
          <button className="bf-action-link" type="button" onClick={(event) => { event.stopPropagation(); setEditing(row); }}>
            编辑
          </button>
          <button className="bf-action-link danger" type="button" onClick={(event) => { event.stopPropagation(); setStatusTarget(row); }}>
            {row.status === "active" ? "停用" : "启用"}
          </button>
          <button className="bf-action-link" type="button" onClick={(event) => { event.stopPropagation(); setResetTarget({ row, password: makePassword() }); }}>
            重置密码
          </button>
        </div>
      ),
    },
  ];

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editing === "create") {
      createMutation.mutate({
        admin_code: form.admin_code.trim(),
        name: form.name.trim(),
        email: form.email.trim() || undefined,
        password: form.password,
        is_super_admin: form.is_super_admin,
        status: form.status,
      });
    } else if (editing) {
      updateMutation.mutate({
        row: editing,
        body: {
          name: form.name.trim(),
          email: form.email.trim(),
          is_super_admin: form.is_super_admin,
          status: form.status,
        },
      });
    }
  };

  if (admins.isLoading) {
    return (
      <div className="bf-super-page">
        <SkeletonBlock className="h-[78px]" />
        <SkeletonBlock className="h-[560px]" />
      </div>
    );
  }

  if (admins.isError || !admins.data) return <ErrorState onRetry={() => admins.refetch()} />;

  return (
    <div className="bf-super-page">
      <Toolbar
        action={<IconButton icon="plus" onClick={() => setEditing("create")}>新增管理员</IconButton>}
      >
        <SearchInput value={keyword} onChange={setKeyword} placeholder="搜索管理员编号 / 姓名 / 邮箱" />
        <SegmentedFilter label="角色" value={role} onChange={setRole} options={[{ label: "全部", value: "" }, { label: "超级管理员", value: "super" }, { label: "普通管理员", value: "admin" }]} />
        <SegmentedFilter label="状态" value={status} onChange={setStatus} options={[{ label: "全部", value: "" }, { label: "启用", value: "active" }, { label: "停用", value: "disabled" }]} />
      </Toolbar>

      <section className="bf-super-card flex min-h-0 flex-1 flex-col p-4">
        <DataTable rows={rows} columns={columns} rowKey={(row) => row.admin_code} selectedKey={selected?.admin_code} onRowClick={setSelected} empty="没有符合条件的管理员账号" />
        <Pagination total={total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
      </section>

      <CenterModal open={Boolean(selected)} width={620} title={selected?.name || "管理员详情"} subtitle={selected?.admin_code} onClose={() => setSelected(null)}>
        {selected ? (
          <>
            <Field label="角色"><RoleTag isSuperAdmin={selected.is_super_admin} /></Field>
            <Field label="状态"><StatusTag status={selected.status} /></Field>
            <Field label="邮箱">{selected.email || "-"}</Field>
            <Field label="权限模板">{templateLabel(selected.permission_template)}</Field>
            <Field label="管理范围">{scopeLabel(selected.managed_scope)}</Field>
            <Field label="最近登录">{formatDateTime(selected.last_login_at)}</Field>
            <Field label="登录 IP">{selected.last_login_ip || "-"}</Field>
            <Field label="创建时间">{formatDateTime(selected.created_at)}</Field>
            <div className="mt-6">
              <div className="mb-3 text-[15px] font-black text-[#071434]">最近登录记录</div>
              <div className="grid gap-2">
                {(selectedEvents.data?.items ?? []).length ? selectedEvents.data?.items.map((item) => (
                  <div key={String(item.id)} className="grid grid-cols-[minmax(0,1fr)_78px] items-center gap-2 rounded-[7px] border border-[#e7eef8] px-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate text-[13px] font-black text-[#263653]">{loginEventLabel(String(item.event_type || ""))}</div>
                      <div className="truncate text-[12px] font-bold text-[#64718d]">{formatDateTime(item.created_at)} · {String(item.ip_address || "-")}</div>
                    </div>
                    <ResultTag result={loginResult(String(item.event_type || ""))} />
                  </div>
                )) : <div className="bf-empty-state min-h-[100px]">暂无登录记录</div>}
              </div>
            </div>
          </>
        ) : null}
      </CenterModal>

      {editing ? (
        <AdminFormModal
          mode={editing === "create" ? "create" : "edit"}
          form={form}
          pending={createMutation.isPending || updateMutation.isPending}
          onChange={(patch) => setForm((current) => ({ ...current, ...patch }))}
          onClose={() => setEditing(null)}
          onSubmit={handleSubmit}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(statusTarget)}
        title={statusTarget?.status === "active" ? "停用管理员账号" : "启用管理员账号"}
        message={statusTarget ? `确认${statusTarget.status === "active" ? "停用" : "启用"} ${statusTarget.name || statusTarget.admin_code}？该操作会写入审计记录。` : ""}
        confirmText={statusTarget?.status === "active" ? "停用" : "启用"}
        tone={statusTarget?.status === "active" ? "danger" : "primary"}
        loading={statusMutation.isPending}
        onCancel={() => setStatusTarget(null)}
        onConfirm={() => statusTarget && statusMutation.mutate({ row: statusTarget, nextStatus: statusTarget.status === "active" ? "disabled" : "active" })}
      />

      <ConfirmDialog
        open={Boolean(resetTarget)}
        title="重置管理员密码"
        message={resetTarget ? (
          <div>
            <div>确认重置 {resetTarget.row.name || resetTarget.row.admin_code} 的密码？</div>
            <div className="mt-3 rounded-[7px] bg-[#f4f7fb] px-3 py-2 font-black text-[#071434]">{resetTarget.password}</div>
          </div>
        ) : null}
        confirmText="确认重置"
        tone="danger"
        loading={resetMutation.isPending}
        onCancel={() => setResetTarget(null)}
        onConfirm={() => resetTarget && resetMutation.mutate(resetTarget)}
      />
    </div>
  );
}
