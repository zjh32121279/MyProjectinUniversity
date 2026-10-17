import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { analyticsApi } from "@/api/analytics";
import { readersApi } from "@/api/readers";
import { ActionButton } from "@/components/ui/ActionButton";
import { DataTable, DataTablePagination, type DataColumn } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { FormDialog } from "@/components/ui/FormDialog";
import { SearchInput } from "@/components/ui/SearchInput";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { AnyRecord } from "@/types/api";
import { formatNumber } from "@/utils/format";
import { formatReaderType } from "@/utils/labels";
import rhythm from "@/styles/AdminRhythm.module.css";

type ReaderStatusTone = "green" | "orange" | "red";
type ReaderForm = { reader_code: string; name: string; reader_type_code: string; phone_masked: string; email: string; status?: string };
type PasswordNotice = { title: string; readerCode: string; loginName: string; password: string; credentialCreated?: boolean };

const emptyForm: ReaderForm = { reader_code: "", name: "", reader_type_code: "adult", phone_masked: "", email: "", status: "active" };

function creditStatus(row: AnyRecord): { label: string; tone: ReaderStatusTone } {
  if (row.borrow_suspended) return { label: "暂停", tone: "red" };
  const score = Number(row.credit_score ?? 0);
  if (score >= 80) return { label: "良好", tone: "green" };
  return { label: "受限", tone: "orange" };
}

function formatReaderStatusLabel(status: unknown): string {
  const key = String(status ?? "").trim();
  const labels: Record<string, string> = {
    active: "正常",
    inactive: "停用",
    suspended: "暂停借阅",
    restored: "已恢复",
  };
  return labels[key] ?? (key || "—");
}

function formatActivityReason(reason: unknown): string {
  const key = String(reason ?? "").trim();
  const labels: Record<string, string> = {
    manual_suspend: "管理员操作",
    manual_restore: "管理员操作",
    system_suspend: "系统自动",
    system_restore: "系统自动",
    overdue: "逾期触发",
    credit_low: "信用过低",
  };
  return labels[key] ?? (key || "—");
}

function formatActivityDetail(detail: unknown): string {
  const text = String(detail ?? "").trim();
  if (!text) return "";
  // Map status transition patterns like "active → suspended"
  return text
    .replace(/\bactive\b/g, "正常")
    .replace(/\binactive\b/g, "停用")
    .replace(/\bsuspended\b/g, "暂停借阅")
    .replace(/\brestored\b/g, "已恢复");
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="grid gap-1 text-sm font-bold text-[#31405f]"><span>{label}</span>{children}</label>;
}

function readerAvatarUrl(row: AnyRecord) {
  const raw = String(row.avatar_url ?? "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/")) return raw;
  return `/${raw}`;
}

function ReaderAvatar({ reader, size = "md" }: { reader: AnyRecord; size?: "md" | "lg" }) {
  const [failed, setFailed] = useState(false);
  const src = !failed ? readerAvatarUrl(reader) : "";
  const initial = String(reader.name ?? reader.reader_code ?? "读").trim().slice(0, 1) || "读";
  const sizeClass = size === "lg" ? "h-14 w-14 text-[18px]" : "h-10 w-10 text-[14px]";

  return (
    <span className={`${sizeClass} grid shrink-0 place-items-center overflow-hidden rounded-full bg-[#eaf2ff] font-black text-[var(--bf-brand)] ring-1 ring-[#d9e6ff]`}>
      {src ? <img className="h-full w-full object-cover" src={src} alt="" onError={() => setFailed(true)} /> : initial}
    </span>
  );
}

export function ReadersPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [readerType, setReaderType] = useState("");
  const [creditFilter, setCreditFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedReader, setSelectedReader] = useState<AnyRecord | null>(null);
  const [drawerMode, setDrawerMode] = useState<"detail" | "activity" | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [formData, setFormData] = useState<ReaderForm>(emptyForm);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [passwordTarget, setPasswordTarget] = useState<string>("");
  const [passwordForm, setPasswordForm] = useState({ newPassword: "", confirmPassword: "" });
  const [passwordNotice, setPasswordNotice] = useState<PasswordNotice | null>(null);
  const pageSize = 8;
  const analytics = useQuery({ queryKey: ["analytics", "readers"], queryFn: analyticsApi.readers });
  const readerQuery = useQuery({
    queryKey: ["readers", keyword, readerType, creditFilter, statusFilter, page, pageSize],
    queryFn: () => readersApi.list({ keyword: keyword || undefined, reader_type_code: readerType || undefined, credit_status: creditFilter || undefined, status: statusFilter || undefined, limit: pageSize, offset: (page - 1) * pageSize }),
  });
  const detailQuery = useQuery({
    queryKey: ["reader-detail", selectedReader?.reader_code],
    queryFn: () => readersApi.detail(String(selectedReader?.reader_code)),
    enabled: Boolean(selectedReader?.reader_code && drawerMode === "detail"),
  });
  const activityQuery = useQuery({
    queryKey: ["reader-activity", selectedReader?.reader_code],
    queryFn: () => readersApi.activity(String(selectedReader?.reader_code)),
    enabled: Boolean(selectedReader?.reader_code && drawerMode === "activity"),
  });
  const recentActivityQuery = useQuery({
    queryKey: ["readers", "recent-activity"],
    queryFn: () => readersApi.recentActivity(20),
    enabled: drawerMode === "activity" && !selectedReader?.reader_code,
  });
  const refreshReaders = async () => {
    await Promise.all([queryClient.invalidateQueries({ queryKey: ["readers"] }), queryClient.invalidateQueries({ queryKey: ["analytics", "readers"] })]);
  };
  const saveMutation = useMutation({
    mutationFn: () => editingCode ? readersApi.update(editingCode, formData) : readersApi.create(formData),
    onSuccess: async (result) => {
      const created = !editingCode;
      toast.success(created ? "读者已新增" : "读者信息已更新");
      if (created && result.initial_password) {
        setPasswordNotice({
          title: "读者已新增",
          readerCode: String(result.reader_code ?? formData.reader_code),
          loginName: String(result.login_name ?? result.reader_code ?? formData.reader_code),
          password: String(result.initial_password),
        });
      }
      setFormOpen(false);
      setEditingCode(null);
      setFormData(emptyForm);
      await refreshReaders();
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ row, action }: { row: AnyRecord; action: "suspend" | "restore" }) => action === "suspend" ? readersApi.suspend(String(row.reader_code)) : readersApi.restore(String(row.reader_code)),
    onSuccess: async () => { toast.success("读者状态已更新"); await refreshReaders(); },
  });
  const resetPasswordMutation = useMutation({
    mutationFn: ({ readerCode, newPassword, confirmPassword }: { readerCode: string; newPassword: string; confirmPassword: string }) => readersApi.resetPassword(readerCode, newPassword, confirmPassword),
    onSuccess: async (result) => {
      toast.success("密码已重置");
      setPasswordNotice({
        title: "密码已重置",
        readerCode: String(result.reader_code ?? passwordTarget),
        loginName: String(result.login_name ?? passwordTarget),
        password: String(result.temporary_password ?? passwordForm.newPassword),
        credentialCreated: Boolean(result.credential_created),
      });
      setPasswordDialogOpen(false);
      setPasswordForm({ newPassword: "", confirmPassword: "" });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "密码重置失败");
    },
  });
  const openPasswordDialog = (readerCode: string) => {
    setPasswordTarget(readerCode);
    setPasswordForm({ newPassword: "", confirmPassword: "" });
    setPasswordDialogOpen(true);
  };
  const handlePasswordSubmit = () => {
    if (passwordForm.newPassword.length < 6) { toast.error("密码至少 6 位"); return; }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) { toast.error("两次输入的密码不一致"); return; }
    resetPasswordMutation.mutate({ readerCode: passwordTarget, newPassword: passwordForm.newPassword, confirmPassword: passwordForm.confirmPassword });
  };
  const openCreate = () => { setEditingCode(null); setFormData(emptyForm); setFormOpen(true); };
  const openEdit = (row: AnyRecord) => { setEditingCode(String(row.reader_code)); setFormData({ reader_code: String(row.reader_code ?? ""), name: String(row.name ?? ""), reader_type_code: String(row.reader_type_code ?? "adult"), phone_masked: String(row.phone_masked ?? ""), email: String(row.email ?? ""), status: String(row.status ?? "active") }); setFormOpen(true); };
  const copyPasswordNotice = async () => {
    if (!passwordNotice?.password) return;
    try {
      await navigator.clipboard.writeText(passwordNotice.password);
      toast.success("密码已复制");
    } catch {
      toast.error("复制失败，请手动选择密码");
    }
  };

  const columns: DataColumn<AnyRecord>[] = [
    {
      key: "reader",
      title: "读者",
      width: "140px",
      render: (row) => (
        <div className="flex min-w-0 items-center gap-3">
          <ReaderAvatar reader={row} />
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-black text-[#101a35]">{String(row.name ?? "-")}</span>
            <span className="mt-0.5 block truncate text-[11.5px] font-bold text-[#64718d]">{String(row.reader_code ?? "-")}</span>
          </span>
        </div>
      ),
    },
    { key: "type", title: "读者类型", width: "94px", render: (row) => <StatusBadge value={formatReaderType(row.reader_type_code)} tone={row.reader_type_code === "institution" ? "cyan" : "blue"} /> },
    { key: "phone_masked", title: "手机号", width: "124px", nowrap: true, render: (row) => <span className="whitespace-nowrap font-semibold text-[#1f2a44]">{String(row.phone_masked || "-")}</span> },
    { key: "email", title: "邮箱", width: "180px", render: (row) => <span className="truncate font-semibold text-[#1f2a44]">{String(row.email || "-")}</span> },
    { key: "credit", title: "信用分", width: "64px", align: "center", render: (row) => <span className="font-black text-[#071334]">{formatNumber(row.credit_score)}</span> },
    { key: "credit_status", title: "信用状态", width: "74px", align: "center", render: (row) => { const status = creditStatus(row); return <StatusBadge value={status.label} tone={status.tone} />; } },
    { key: "max", title: "最大在借", width: "68px", align: "center", nowrap: true, render: (row) => <span className="font-semibold text-[#1f2a44]">{formatNumber(row.max_borrow_count)}</span> },
    { key: "current", title: "当前在借", width: "68px", align: "center", nowrap: true, render: (row) => <span className="font-semibold text-[#1f2a44]">{formatNumber(row.current_borrow_count)}</span> },
    { key: "actions", title: "操作", width: "210px", align: "center", nowrap: true, render: (row) => (<div className="mx-auto inline-flex shrink-0 items-center justify-center gap-3 text-sm font-bold text-[var(--bf-brand)]"><button type="button" onClick={() => { setSelectedReader(row); setDrawerMode("detail"); }}>查看</button><button type="button" onClick={() => openEdit(row)}>编辑</button><button type="button" onClick={() => openPasswordDialog(String(row.reader_code))}>密码</button><button type="button" onClick={() => { setSelectedReader(row); setDrawerMode("activity"); }}>更多</button></div>) },
  ];

  if (analytics.isError || readerQuery.isError) return <ErrorState onRetry={() => void Promise.all([analytics.refetch(), readerQuery.refetch()])} />;

  const data = analytics.data ?? {};
  const rows = readerQuery.data?.items ?? [];
  const hasTableContent = analytics.isLoading || readerQuery.isLoading || rows.length > 0;
  const total = data.registered_reader_count ?? readerQuery.data?.total;
  const activityData = (activityQuery.data ?? {}) as AnyRecord;
  const activityLoans = Array.isArray(activityData.loans) ? (activityData.loans as AnyRecord[]) : [];
  const activityStatusEvents = Array.isArray(activityData.status_events) ? (activityData.status_events as AnyRecord[]) : [];
  const activityCreditEvents = Array.isArray(activityData.credit_events) ? (activityData.credit_events as AnyRecord[]) : [];
  const recentActivityData = (recentActivityQuery.data ?? {}) as AnyRecord;
  const recentActivities = Array.isArray(recentActivityData.items) ? (recentActivityData.items as AnyRecord[]) : [];
  const statCards = [
    { title: "读者总数", value: formatNumber(data.registered_reader_count ?? total), unit: "人", icon: "readers", tone: "blue" as const },
    { title: "正常读者", value: formatNumber(data.normal_reader_count), unit: "人", icon: "success", tone: "green" as const },
    { title: "信用受限", value: formatNumber(data.credit_limited_count), unit: "人", icon: "risk", tone: "orange" as const },
    { title: "暂停借阅", value: formatNumber(data.suspended_count), unit: "人", icon: "overdue", tone: "purple" as const },
    { title: "今日新增", value: formatNumber(data.today_new_reader_count), unit: "人", icon: "analysis", tone: "cyan" as const },
  ];

  return (
    <div className={rhythm.compactPage}>
      <div className={rhythm.readersHeader}>
        <div className="flex h-[52px] items-center justify-between gap-4"><p className="text-[18px] font-bold leading-relaxed text-[#31405f]">读者信息、信用状态和在借统计均来自 Core 数据库。</p><ActionButton variant="secondary" icon="calendar" onClick={() => { setSelectedReader(null); setDrawerMode("activity"); }}>读者动态</ActionButton></div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">{statCards.map((card) => <StatCard key={card.title} {...card} compact className={rhythm.readerStatCard} />)}</div>
      <div className={`bf-card overflow-hidden bg-white ${rhythm.pagedCard} ${hasTableContent ? rhythm.readersCard : rhythm.emptyTableCard}`}>
        <FilterBar className={rhythm.readerFilter}>
          <SearchInput className="w-full max-w-[330px]" value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1); }} placeholder="搜索读者编号、姓名、手机号" />
          <FilterSelect value={readerType} onChange={(event) => { setReaderType(event.target.value); setPage(1); }}><option value="">读者类型：全部</option><option value="adult">成人读者</option><option value="teen">青少年读者</option><option value="child">儿童读者</option><option value="senior">老年读者</option><option value="institution">机构账号</option></FilterSelect>
          <FilterSelect value={creditFilter} onChange={(event) => { setCreditFilter(event.target.value); setPage(1); }}><option value="">信用状态：全部</option><option value="good">良好</option><option value="limited">受限</option><option value="suspended">暂停</option></FilterSelect>
          <FilterSelect value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="">借阅状态：全部</option><option value="active">正常</option><option value="inactive">停用</option></FilterSelect>
          <ActionButton className="ml-auto" icon="plus" onClick={openCreate}>新增读者</ActionButton>
        </FilterBar>
        {hasTableContent ? <DataTable rows={rows} columns={columns} loading={analytics.isLoading || readerQuery.isLoading} emptyTitle="暂无读者记录" emptyMode="none" className={`${rhythm.pagedTable} ${rhythm.readersTable} [&_table]:table-fixed [&_table]:min-w-[1060px]`} footer={<DataTablePagination total={readerQuery.data?.total ?? 0} page={page} pageSize={pageSize} onPageChange={setPage} />} /> : null}
      </div>

      <FormDialog open={drawerMode !== null && !formOpen} onOpenChange={(open) => !open && setDrawerMode(null)} title={drawerMode === "activity" ? (selectedReader ? `${String(selectedReader.name ?? selectedReader.reader_code)} · 读者动态` : "最近读者动态") : "读者详情"}>
        {drawerMode === "activity" ? (
          selectedReader ? (
            /* ── 单个读者的读者动态 ── */
            activityQuery.isLoading ? <div className="text-sm font-semibold text-[#64718d]">加载中…</div> : (
              <div className="space-y-5 text-sm">
                {/* summary */}
                <div className="grid grid-cols-3 gap-2 rounded-2xl border border-[#e7edf7] bg-[#f8fbff] p-3 text-center">
                  <div><div className="text-[20px] font-black text-[#101a35]">{formatNumber(activityData.active_borrow_count)}</div><div className="mt-0.5 text-[11px] font-bold text-[#64718d]">在借</div></div>
                  <div><div className="text-[20px] font-black text-[#101a35]">{formatNumber(activityData.returned_count)}</div><div className="mt-0.5 text-[11px] font-bold text-[#64718d]">已还</div></div>
                  <div><div className="text-[20px] font-black text-[#101a35]">{formatNumber(activityData.reservation_count)}</div><div className="mt-0.5 text-[11px] font-bold text-[#64718d]">预约</div></div>
                </div>
                {/* loan history */}
                {activityLoans.length ? (
                  <div>
                    <div className="mb-2 text-[13px] font-black text-[#31405f]">借阅记录</div>
                    <div className="space-y-2">
                      {activityLoans.map((loan, idx) => (
                        <div key={idx} className="rounded-xl border border-[#e7edf7] bg-[#f8fbff] px-3 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-[13px] font-bold text-[#101a35]">{String(loan.book_title ?? loan.book_code ?? "—")}</span>
                            <StatusBadge value={loan.status === "returned" ? "已还" : loan.status === "overdue" ? "逾期" : "在借"} tone={loan.status === "returned" ? "green" : loan.status === "overdue" ? "red" : "blue"} />
                          </div>
                          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] font-semibold text-[#64718d]">
                            <span>借出 {String(loan.borrowed_at ?? "—").slice(0, 10)}</span>
                            {loan.returned_at ? <span>归还 {String(loan.returned_at).slice(0, 10)}</span> : <span>到期 {String(loan.due_at ?? "—").slice(0, 10)}</span>}
                            {loan.renewal_count ? <span>续借 {formatNumber(loan.renewal_count)} 次</span> : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : <div className="text-[13px] font-semibold text-[#64718d]">暂无借阅记录</div>}
                {/* status events */}
                {activityStatusEvents.length ? (
                  <div>
                    <div className="mb-2 text-[13px] font-black text-[#31405f]">状态变更</div>
                    <div className="space-y-1.5">
                      {activityStatusEvents.map((e, idx) => (
                        <div key={idx} className="flex items-center justify-between rounded-lg px-2 py-1 text-[12px] font-semibold text-[#64718d]">
                          <span>{formatReaderStatusLabel(e.old_status)} → {formatReaderStatusLabel(e.new_status)} · {formatActivityReason(e.reason)}</span>
                          <span>{String(e.created_at ?? "").slice(0, 10)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {/* credit events */}
                {activityCreditEvents.length ? (
                  <div>
                    <div className="mb-2 text-[13px] font-black text-[#31405f]">信用变更</div>
                    <div className="space-y-1.5">
                      {activityCreditEvents.map((e, idx) => (
                        <div key={idx} className="flex items-center justify-between rounded-lg px-2 py-1 text-[12px] font-semibold">
                          <span className={Number(e.delta) >= 0 ? "text-[#0bae72]" : "text-[#dc2626]"}>{Number(e.delta) >= 0 ? "+" : ""}{String(e.delta ?? 0)} · {String(e.old_score ?? "-")} → {String(e.new_score ?? "-")}</span>
                          <span className="text-[#64718d]">{String(e.created_at ?? "").slice(0, 10)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="flex gap-2 pt-1">
                  <ActionButton size="sm" variant="warning" onClick={() => selectedReader.reader_code && statusMutation.mutate({ row: selectedReader, action: "suspend" })}>暂停借阅</ActionButton>
                  <ActionButton size="sm" variant="success" onClick={() => selectedReader.reader_code && statusMutation.mutate({ row: selectedReader, action: "restore" })}>恢复借阅</ActionButton>
                </div>
              </div>
            )
          ) : (
            /* ── 全局最近读者动态 ── */
            recentActivityQuery.isLoading ? <div className="text-sm font-semibold text-[#64718d]">加载中…</div> : (
              recentActivities.length ? (
                <div className="space-y-2">
                  {recentActivities.map((item, idx) => (
                    <div key={idx} className="rounded-xl border border-[#e7edf7] bg-[#f8fbff] px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-bold text-[#101a35]">{String(item.reader_name ?? item.reader_code ?? "—")}</span>
                        <span className="text-[11px] font-semibold text-[#64718d]">{String(item.time ?? "").slice(0, 10)}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[12px] font-semibold">
                        <span className="rounded-md bg-[#eef3ff] px-1.5 py-0.5 text-[#4f46e5]">{String(item.action)}</span>
                        {item.book_title ? <span className="text-[#31405f]">{String(item.book_title)}</span> : null}
                        {item.detail ? <span className="text-[#64718d]">{formatActivityDetail(item.detail)}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-sm font-semibold text-[#64718d]">暂无读者动态</div>
            )
          )
        ) : (
          /* ── 读者详情 ── */
          selectedReader ? (
            <div className="grid gap-3 text-sm font-semibold text-[#31405f]">
              {detailQuery.isLoading ? (
                <div className="text-sm font-semibold text-[#64718d]">加载中…</div>
              ) : (() => {
                const detail = detailQuery.data ?? selectedReader;
                const fields: [string, unknown][] = [
                  ["读者编号", detail.reader_code],
                  ["姓名", detail.name],
                  ["读者类型", formatReaderType(detail.reader_type_code)],
                  ["手机号", detail.phone_masked],
                  ["邮箱", detail.email],
                  ["账号状态", String(detail.status ?? "") === "active" ? "正常" : String(detail.status ?? "") === "inactive" ? "停用" : detail.status],
                  ["信用分", formatNumber(detail.credit_score)],
                  ["信用状态", detail.credit_status],
                  ["当前在借", formatNumber(detail.current_borrow_count)],
                  ["最大在借", formatNumber(detail.max_borrow_count)],
                  ["注册时间", String(detail.registered_at ?? "").slice(0, 10)],
                ];
                if (detail.borrow_suspended_until) {
                  fields.push(["暂停借阅至", String(detail.borrow_suspended_until).slice(0, 10)]);
                }
                return (
                  <>
                    <div className="flex items-center gap-3 rounded-2xl border border-[#e1e9f6] bg-[#f8fbff] p-3">
                      <ReaderAvatar reader={detail} size="lg" />
                      <div className="min-w-0">
                        <div className="truncate text-[18px] font-black text-[#101a35]">{String(detail.name ?? "—")}</div>
                        <div className="mt-1 truncate text-[12px] font-bold text-[#64718d]">{String(detail.reader_code ?? "—")} · {formatReaderType(detail.reader_type_code)}</div>
                      </div>
                    </div>
                    {fields.map(([label, value]) => (
                      <div key={label} className="rounded-xl border border-[#e7edf7] bg-[#f8fbff] px-3 py-2">
                        <span className="text-[#64718d]">{label}</span>
                        <div className="mt-1 break-all text-[#10203f]">{String(value ?? "—")}</div>
                      </div>
                    ))}
                  </>
                );
              })()}
              <div className="mt-2 flex gap-2">
                <ActionButton size="sm" variant="warning" onClick={() => selectedReader.reader_code && statusMutation.mutate({ row: selectedReader, action: "suspend" })}>暂停借阅</ActionButton>
                <ActionButton size="sm" variant="success" onClick={() => selectedReader.reader_code && statusMutation.mutate({ row: selectedReader, action: "restore" })}>恢复借阅</ActionButton>
              </div>
            </div>
          ) : <div className="text-sm font-semibold text-[#64718d]">请选择一位读者查看详情。</div>
        )}
      </FormDialog>

      <FormDialog open={formOpen} onOpenChange={setFormOpen} title={editingCode ? "编辑读者" : "新增读者"}>
        <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
          <Field label="读者编号"><input className="bf-input" value={formData.reader_code} disabled={Boolean(editingCode)} onChange={(event) => setFormData((data) => ({ ...data, reader_code: event.target.value }))} required /></Field>
          <Field label="姓名"><input className="bf-input" value={formData.name} onChange={(event) => setFormData((data) => ({ ...data, name: event.target.value }))} required /></Field>
          <Field label="读者类型"><select className="bf-input" value={formData.reader_type_code} onChange={(event) => setFormData((data) => ({ ...data, reader_type_code: event.target.value }))}><option value="child">儿童</option><option value="teen">青少年</option><option value="adult">成人</option><option value="senior">老年</option><option value="institution">机构</option></select></Field>
          <Field label="手机号"><input className="bf-input" value={formData.phone_masked} onChange={(event) => setFormData((data) => ({ ...data, phone_masked: event.target.value }))} /></Field>
          <Field label="邮箱"><input className="bf-input" type="email" value={formData.email} onChange={(event) => setFormData((data) => ({ ...data, email: event.target.value }))} /></Field>
          <div className="mt-2 flex items-center justify-end gap-2">
            <ActionButton type="button" variant="secondary" onClick={() => setFormOpen(false)}>取消</ActionButton><ActionButton type="submit" disabled={saveMutation.isPending}>{saveMutation.isPending ? "保存中" : "保存"}</ActionButton>
          </div>
        </form>
      </FormDialog>

      <FormDialog open={passwordDialogOpen} onOpenChange={setPasswordDialogOpen} title="重置读者密码">
        <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); handlePasswordSubmit(); }}>
          <Field label="新密码"><input className="bf-input" type="password" value={passwordForm.newPassword} onChange={(event) => setPasswordForm((data) => ({ ...data, newPassword: event.target.value }))} placeholder="至少 6 位" required /></Field>
          <Field label="确认密码"><input className="bf-input" type="password" value={passwordForm.confirmPassword} onChange={(event) => setPasswordForm((data) => ({ ...data, confirmPassword: event.target.value }))} placeholder="再次输入新密码" required /></Field>
          <div className="mt-2 flex justify-end gap-2">
            <ActionButton type="button" variant="secondary" onClick={() => setPasswordDialogOpen(false)}>取消</ActionButton>
            <ActionButton type="submit" disabled={resetPasswordMutation.isPending}>{resetPasswordMutation.isPending ? "重置中" : "确认重置"}</ActionButton>
          </div>
        </form>
      </FormDialog>

      <FormDialog open={Boolean(passwordNotice)} onOpenChange={(open) => !open && setPasswordNotice(null)} title={passwordNotice?.title ?? "读者登录密码"}>
        {passwordNotice ? (
          <div className="grid gap-3 text-sm font-semibold text-[#31405f]">
            <div className="rounded-xl border border-[#e7edf7] bg-[#f8fbff] px-3 py-2">
              <span className="text-[#64718d]">登录账号</span>
              <div className="mt-1 break-all text-[16px] font-black text-[#10203f]">{passwordNotice.loginName}</div>
            </div>
            <div className="rounded-xl border border-[#e7edf7] bg-[#fffdf5] px-3 py-2">
              <span className="text-[#64718d]">临时密码</span>
              <div className="mt-1 break-all font-mono text-[20px] font-black tracking-normal text-[#b45309]">{passwordNotice.password}</div>
            </div>
            <div className="rounded-xl bg-[#f8fafc] px-3 py-2 text-[12px] leading-5 text-[#64718d]">
              密码只在本次操作后显示一次，系统不会保存明文密码。关闭后无法再次查看，只能重新重置。
              {passwordNotice.credentialCreated ? " 该读者原本没有登录凭据，本次已自动补建。" : ""}
            </div>
            <div className="mt-1 flex justify-end gap-2">
              <ActionButton type="button" variant="secondary" onClick={copyPasswordNotice}>复制密码</ActionButton>
              <ActionButton type="button" onClick={() => setPasswordNotice(null)}>我已记录</ActionButton>
            </div>
          </div>
        ) : null}
      </FormDialog>
    </div>
  );
}
