import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { notificationsApi } from "@/api/notifications";
import { readersApi } from "@/api/readers";
import { AppIcon } from "@/components/icons/AppIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { DataTable, DataTablePagination, type DataColumn } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { FormDialog } from "@/components/ui/FormDialog";
import { PageCard } from "@/components/ui/PageCard";
import { SearchInput } from "@/components/ui/SearchInput";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { AnyRecord } from "@/types/api";
import { formatDateTime, formatNumber } from "@/utils/format";
import { formatNotificationTitle, formatNotificationType, formatSecondaryText } from "@/utils/labels";
import rhythm from "@/styles/AdminRhythm.module.css";

type NotificationTab = "all" | "system" | "due" | "overdue" | "reservation" | "task" | "other";
type NotificationTargetType = "all_readers" | "all_admins" | "all" | "reader" | "admin";

type NotificationFormState = {
  title: string;
  content: string;
  notification_type: string;
  target_type: NotificationTargetType;
  recipient_ids: string[];
  mode: "draft" | "send";
};

const initialNotificationForm: NotificationFormState = {
  title: "",
  content: "",
  notification_type: "general",
  target_type: "all_readers",
  recipient_ids: [],
  mode: "draft",
};

const notificationTabs: Array<{ key: NotificationTab; label: string; type?: string }> = [
  { key: "all", label: "全部" },
  { key: "system", label: "系统通知", type: "system" },
  { key: "due", label: "到期提醒", type: "due" },
  { key: "overdue", label: "逾期提醒", type: "overdue" },
  { key: "reservation", label: "预约通知", type: "reservation" },
  { key: "task", label: "任务提醒", type: "task" },
  { key: "other", label: "其他", type: "other" },
];

function lifecycleStatusView(status: string) {
  const map: Record<string, { label: string; tone: "green" | "red" | "blue" | "purple" | "orange" }> = {
    draft: { label: "草稿", tone: "blue" },
    queued: { label: "待发送", tone: "orange" },
    sending: { label: "发送中", tone: "purple" },
    completed: { label: "已完成", tone: "green" },
    failed: { label: "失败", tone: "red" },
    cancelled: { label: "已取消", tone: "blue" },
  };
  return map[status] ?? { label: status || "—", tone: "blue" as const };
}

function formatScope(row: AnyRecord) {
  const scope = row.target_scope_json;
  if (!scope) return "—";
  try {
    const parsed = typeof scope === "string" ? JSON.parse(scope) : scope;
    if (parsed.all_readers) return "全体读者";
    if (parsed.all_admins) return "全体管理员";
    if (parsed.reader_count) return `${parsed.reader_count} 位读者`;
    if (parsed.admin_count) return `${parsed.admin_count} 位管理员`;
  } catch {
    // fall through
  }
  return String(scope).slice(0, 60);
}

function valueText(value: unknown, fallback = "") {
  return String(value ?? "").trim() || fallback;
}

function recipientValue(item: AnyRecord) {
  return valueText(item.code ?? item.reader_code ?? item.admin_code ?? item.id);
}

function recipientName(item: AnyRecord) {
  return valueText(item.name, recipientValue(item) || "未命名");
}

function recipientDescription(item: AnyRecord, targetType: "reader" | "admin") {
  const description = valueText(item.description);
  const code = recipientValue(item);
  if (description && code) return `${code} · ${description}`;
  if (code) return code;
  return targetType === "reader" ? "读者" : "管理员";
}

function avatarUrl(item: AnyRecord) {
  const raw = valueText(item.avatar_url);
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw) || raw.startsWith("/")) return raw;
  return `/${raw}`;
}

function RecipientAvatar({ item, selected, targetType }: { item: AnyRecord; selected: boolean; targetType: "reader" | "admin" }) {
  const [failed, setFailed] = useState(false);
  const raw = String(item.avatar_url ?? "").trim();
  const src = targetType === "reader" && !failed && raw ? raw : "";
  const initial = String(item.name ?? item.code ?? "").trim().slice(0, 1) || (targetType === "reader" ? "读" : "管");

  return (
    <span className={`grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-full text-sm font-black ${selected ? "bg-[var(--bf-brand)] text-white ring-2 ring-[var(--bf-brand)] ring-offset-1" : "bg-[#eaf2ff] text-[var(--bf-brand)]"}`}>
      {src ? <img className="h-full w-full object-cover" src={src} alt="" onError={() => setFailed(true)} /> : initial}
    </span>
  );
}

function splitRecipientValues(value: string) {
  return value
    .split(/[,\s，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function uniqueRecipientValues(values: string[]) {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

type RecipientPickerProps = {
  targetType: "reader" | "admin";
  values: string[];
  keyword: string;
  items: AnyRecord[];
  loading: boolean;
  error: boolean;
  fieldClass: string;
  onKeywordChange: (value: string) => void;
  onValuesChange: (value: string[]) => void;
};

function RecipientPicker({
  targetType,
  values,
  keyword,
  items,
  loading,
  error,
  fieldClass,
  onKeywordChange,
  onValuesChange,
}: RecipientPickerProps) {
  const targetLabel = targetType === "reader" ? "读者" : "管理员";
  const placeholder = targetType === "reader" ? "搜索读者姓名 / 编号 / 手机号" : "搜索管理员姓名 / 编号 / 邮箱";
  const selectedValues = uniqueRecipientValues(values);
  const selectedText = selectedValues.join("，");

  const toggleValue = (nextValue: string) => {
    if (!nextValue) return;
    if (selectedValues.includes(nextValue)) {
      onValuesChange(selectedValues.filter((item) => item !== nextValue));
      return;
    }
    onValuesChange([...selectedValues, nextValue]);
  };

  return (
    <div className="overflow-hidden rounded-[14px] border border-[#dce4f2] bg-white">
      <div className="flex items-center gap-3 border-b border-[#edf2f8] p-3">
        <SearchInput
          className="h-10 min-w-0 flex-1"
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
          placeholder={placeholder}
        />
        {selectedValues.length ? (
          <button
            className="h-10 shrink-0 rounded-[8px] border border-[#dce4f2] px-3 text-[13px] font-black text-[#64718d] hover:bg-[#f8fbff]"
            type="button"
            onClick={() => onValuesChange([])}
          >
            清除
          </button>
        ) : null}
      </div>
      <div className="bf-scrollbar max-h-[238px] overflow-y-auto p-2">
        {loading ? (
          <div className="grid gap-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-[58px] animate-pulse rounded-[10px] bg-[#f2f6fb]" />
            ))}
          </div>
        ) : error ? (
          <div className="grid h-[104px] place-items-center text-sm font-bold text-[#ef4444]">搜索失败</div>
        ) : items.length ? (
          <div className="grid gap-2">
            {items.map((item) => {
              const code = recipientValue(item);
              const id = valueText(item.id);
              const itemValue = code || id;
              const selected = Boolean(itemValue && selectedValues.includes(itemValue));
              return (
                <button
                  key={`${targetType}-${id || code}`}
                  type="button"
                  onClick={() => toggleValue(itemValue)}
                  className={`grid h-[58px] w-full grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-3 rounded-[10px] border px-3 text-left transition ${
                    selected
                      ? "border-[var(--bf-brand)] bg-[var(--bf-brand-soft)] shadow-[0_8px_18px_rgba(31,94,255,0.10)]"
                      : "border-[#e8eef6] bg-[#fbfcff] hover:border-[#cbd8ee] hover:bg-[#f8fbff]"
                  }`}
                >
                  <RecipientAvatar item={item} selected={selected} targetType={targetType} />
                  <span className="min-w-0">
                    <span className="block truncate text-[14px] font-black text-[#101a35]">{recipientName(item)}</span>
                    <span className="mt-0.5 block truncate text-[12px] font-bold text-[#64718d]">{recipientDescription(item, targetType)}</span>
                  </span>
                  <StatusBadge value={item.status} tone={valueText(item.status) === "active" ? "green" : "gray"} />
                </button>
              );
            })}
          </div>
        ) : (
          <div className="grid h-[104px] place-items-center text-sm font-bold text-[#64718d]">暂无匹配{targetLabel}</div>
        )}
      </div>
      <div className="grid grid-cols-[86px_minmax(0,1fr)] items-center gap-3 border-t border-[#edf2f8] p-3">
        <span className="text-[13px] font-black text-[#31405f]">已选 {selectedValues.length} 个</span>
        <input
          className={fieldClass}
          value={selectedText}
          onChange={(event) => onValuesChange(uniqueRecipientValues(splitRecipientValues(event.target.value)))}
          placeholder={`${targetLabel}ID或编号，可用逗号分隔多个`}
        />
      </div>
    </div>
  );
}

export function NotificationsPage() {
  const [lifecycleStatus, setLifecycleStatus] = useState("");
  const [keyword, setKeyword] = useState("");
  const [tab, setTab] = useState<NotificationTab>("all");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<NotificationFormState>(initialNotificationForm);
  const [recipientKeyword, setRecipientKeyword] = useState("");
  const [selectedMessage, setSelectedMessage] = useState<AnyRecord | null>(null);
  const pageSize = 6;
  const queryClient = useQueryClient();
  const notificationType = notificationTabs.find((item) => item.key === tab)?.type;
  const isSpecificRecipient = createForm.target_type === "reader" || createForm.target_type === "admin";
  const recipientType = createForm.target_type === "admin" ? "admin" : "reader";

  const statsQuery = useQuery({
    queryKey: ["notifications", "stats"],
    queryFn: notificationsApi.stats,
  });

  const messagesQuery = useQuery({
    queryKey: ["notifications", lifecycleStatus, keyword, notificationType, page, pageSize],
    queryFn: () =>
      notificationsApi.list({
        lifecycle_status: lifecycleStatus || undefined,
        notification_type: notificationType || undefined,
        keyword: keyword || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      }),
  });

  const recipientQuery = useQuery({
    queryKey: ["notifications", "recipient-options", recipientType, recipientKeyword],
    queryFn: async () => {
      if (recipientType === "reader") {
        const data = await readersApi.list({ keyword: recipientKeyword || undefined, limit: 30 });
        return {
          items: (data.items || []).map((r: AnyRecord) => ({ ...r, code: r.reader_code || "", type: "reader" })),
          total: data.total ?? 0,
        };
      }
      return notificationsApi.recipientOptions({
        recipient_type: recipientType,
        keyword: recipientKeyword || undefined,
        limit: 30,
      });
    },
    enabled: createOpen && isSpecificRecipient,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const sendMessage = useMutation({
    mutationFn: notificationsApi.sendMessage,
    onSuccess: () => {
      toast.success("消息已发送");
      invalidate();
    },
    onError: () => toast.error("发送失败，请检查消息状态"),
  });

  const cancelMessage = useMutation({
    mutationFn: notificationsApi.cancelMessage,
    onSuccess: () => {
      toast.success("通知已取消");
      invalidate();
    },
    onError: () => toast.error("取消失败，请检查消息状态"),
  });

  const updateCreateForm = <K extends keyof NotificationFormState>(key: K, value: NotificationFormState[K]) => {
    setCreateForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateTargetType = (value: NotificationTargetType) => {
    setCreateForm((prev) => ({ ...prev, target_type: value, recipient_ids: [] }));
    setRecipientKeyword("");
  };

  const updateCreateOpen = (open: boolean) => {
    setCreateOpen(open);
    if (!open) {
      setCreateForm(initialNotificationForm);
      setRecipientKeyword("");
    }
  };

  const targetScopeJson = () => {
    const base: AnyRecord = { source: "admin_manual" };
    if (createForm.target_type === "all_readers") base.all_readers = true;
    else if (createForm.target_type === "all_admins") base.all_admins = true;
    else if (createForm.target_type === "all") {
      base.all_readers = true;
      base.all_admins = true;
    } else if (createForm.target_type === "reader") {
      base.reader_count = createForm.recipient_ids.length;
      base.recipient_ids = createForm.recipient_ids;
    } else if (createForm.target_type === "admin") {
      base.admin_count = createForm.recipient_ids.length;
      base.recipient_ids = createForm.recipient_ids;
    }
    return JSON.stringify(base);
  };

  const createMessage = useMutation({
    mutationFn: async () => {
      const title = createForm.title.trim();
      const content = createForm.content.trim();
      const recipientIds = uniqueRecipientValues(createForm.recipient_ids);
      if (!title) throw new Error("请填写通知标题");
      if (!content) throw new Error("请填写通知内容");
      if (["reader", "admin"].includes(createForm.target_type) && !recipientIds.length) {
        throw new Error("请选择至少一个指定接收对象");
      }
      const base = {
        title,
        content,
        notification_type: createForm.notification_type,
        source_type: "manual",
        target_scope_json: targetScopeJson(),
      };
      return notificationsApi.batch({
        ...base,
        lifecycle_status: createForm.mode === "draft" ? "draft" : "queued",
        recipients: ["reader", "admin"].includes(createForm.target_type)
          ? recipientIds.map((recipientId) => ({
            recipient_type: createForm.target_type,
            recipient_id: recipientId,
          }))
          : [{ recipient_type: createForm.target_type }],
      });
    },
    onSuccess: () => {
      toast.success(createForm.mode === "draft" ? "通知草稿已创建" : "通知已发送");
      updateCreateOpen(false);
      invalidate();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "通知创建失败");
    },
  });

  const columns: DataColumn<AnyRecord>[] = [
    {
      key: "title",
      title: "通知标题",
      width: "332px",
      render: (row) => (
        <div className="flex items-start gap-3">
          <span className="mt-2.5 h-2.5 w-2.5 rounded-full bg-[var(--bf-brand)]" />
          <div className="min-w-0">
            <div className="font-bold text-[#101a35]">{formatNotificationTitle(row)}</div>
            <div className="mt-1 max-w-[300px] truncate text-xs text-[var(--bf-text-secondary)]">{formatSecondaryText(row.content)}</div>
          </div>
        </div>
      ),
    },
    {
      key: "type",
      title: "通知类型",
      width: "102px",
      render: (row) => (
        <StatusBadge
          value={formatNotificationType(row.notification_type)}
          tone={
            row.notification_type === "reservation" ? "purple"
            : row.notification_type === "overdue" ? "red"
            : row.notification_type === "due" ? "orange"
            : "blue"
          }
        />
      ),
    },
    {
      key: "scope",
      title: "接收范围",
      width: "150px",
      nowrap: true,
      render: (row) => (
        <span className="block max-w-[140px] truncate text-xs text-[var(--bf-text-secondary)]">
          {formatScope(row)}
        </span>
      ),
    },
    {
      key: "lifecycle_status",
      title: "生命周期",
      width: "90px",
      align: "center",
      render: (row) => {
        const sv = lifecycleStatusView(String(row.lifecycle_status ?? ""));
        return <StatusBadge value={sv.label} tone={sv.tone} />;
      },
    },
    {
      key: "delivery_stats",
      title: "投递统计",
      width: "120px",
      align: "center",
      render: (row) => {
        const sent = Number(row.sent_deliveries ?? 0);
        const total = Number(row.total_deliveries ?? 0);
        const failed = Number(row.failed_deliveries ?? 0);
        return (
          <span className="text-xs text-[var(--bf-text-secondary)]">
            {sent}/{total} 已投
            {failed > 0 ? <span className="text-red-500"> · {failed} 失败</span> : null}
          </span>
        );
      },
    },
    {
      key: "created_at",
      title: "创建时间",
      width: "126px",
      nowrap: true,
      render: (row) => (
        <span className="text-[var(--bf-text-secondary)]">
          {formatDateTime(row.updated_at ?? row.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      title: "操作",
      width: "190px",
      align: "center",
      nowrap: true,
      render: (row) => {
        const ls = String(row.lifecycle_status ?? "");
        const canSend = ls === "draft" || ls === "queued";
        const canCancel = ls === "draft" || ls === "queued";
        return (
          <div className="mx-auto inline-flex shrink-0 items-center justify-center gap-2">
            <ActionButton className="h-8 px-2.5 text-xs" size="sm" variant="secondary" icon="eye" onClick={() => setSelectedMessage(row)}>
              查看
            </ActionButton>
            {canSend ? (
              <ActionButton
                className="h-8 px-2.5 text-xs"
                size="sm"
                icon="send"
                disabled={sendMessage.isPending || cancelMessage.isPending}
                onClick={() => sendMessage.mutate(Number(row.id))}
              >
                发送
              </ActionButton>
            ) : null}
            {canCancel ? (
              <ActionButton
                className="h-8 px-2.5 text-xs"
                size="sm"
                variant="danger"
                icon="close"
                disabled={sendMessage.isPending || cancelMessage.isPending}
                onClick={() => {
                  if (window.confirm("确认取消这条通知？取消后不会继续投递。")) {
                    cancelMessage.mutate(Number(row.id));
                  }
                }}
              >
                取消
              </ActionButton>
            ) : null}
          </div>
        );
      },
    },
  ];

  if (statsQuery.isError || messagesQuery.isError) {
    return (
      <ErrorState
        onRetry={() => void Promise.all([statsQuery.refetch(), messagesQuery.refetch()])}
      />
    );
  }

  const stats = statsQuery.data ?? {};
  const rows = messagesQuery.data?.items ?? [];
  const hasTableContent = statsQuery.isLoading || messagesQuery.isLoading || rows.length > 0;

  const statCards = [
    {
      title: "草稿/待发送",
      value: formatNumber(Number(stats.draft_queued_count ?? 0)),
      unit: "条",
      icon: "notification" as const,
      tone: "blue" as const,
    },
    {
      title: "已发送消息",
      value: formatNumber(Number(stats.completed_count ?? 0)),
      unit: "条",
      icon: "send" as const,
      tone: "green" as const,
    },
    {
      title: "失败投递",
      value: formatNumber(Number(stats.failed_delivery_count ?? 0)),
      unit: "条",
      icon: "data" as const,
      tone: "red" as const,
    },
    {
      title: "今日发送",
      value: formatNumber(Number(stats.sent_today_count ?? 0)),
      unit: "条",
      icon: "calendar" as const,
      tone: "orange" as const,
    },
  ];
  const fieldClass = "h-10 w-full rounded-[10px] border border-[#dce4f2] bg-white px-3 text-sm font-bold text-[#101a35] outline-none focus:border-[var(--bf-brand)]";
  const labelClass = "grid gap-1.5 text-[13px] font-black text-[#31405f]";

  return (
    <div className={rhythm.compactPage}>
      <div className="flex h-[52px] items-center">
        <p className="text-[18px] font-bold leading-relaxed text-[#31405f]">
          通知草拟、发送和投递记录均来自 Core 通知服务（消息 + 投递两层模型）。
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} compact className={rhythm.notificationStatCard} />
        ))}
      </div>
      <div className="flex gap-6 border-b border-[var(--bf-border-soft)]">
        {notificationTabs.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => {
              setTab(item.key);
              setPage(1);
            }}
            className={`relative h-11 text-sm font-black ${tab === item.key ? "text-[var(--bf-brand)]" : "text-[#1b2848]"}`}
          >
            {item.label}
            {tab === item.key ? <span className="absolute bottom-0 left-0 h-1 w-full rounded-full bg-[var(--bf-brand)]" /> : null}
          </button>
        ))}
      </div>
      <PageCard
        className={`${rhythm.pagedCard} ${hasTableContent ? rhythm.notificationsCard : rhythm.emptyTableCard}`}
        bodyClassName={rhythm.pagedBody}
      >
        <FilterBar>
          <FilterSelect
            value={lifecycleStatus}
            onChange={(event) => {
              setLifecycleStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="queued">待发送</option>
            <option value="sending">发送中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </FilterSelect>
          <SearchInput
            className="w-full max-w-[280px]"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
            placeholder="搜索标题 / 内容"
          />
          <ActionButton className="ml-auto" icon="plus" onClick={() => updateCreateOpen(true)}>新建通知</ActionButton>
        </FilterBar>
        {hasTableContent ? (
          <DataTable
            rows={rows}
            columns={columns}
            loading={statsQuery.isLoading || messagesQuery.isLoading}
            emptyTitle="暂无通知"
            emptyMode="none"
            className={`${rhythm.pagedTable} ${rhythm.notificationsTable} [&_table]:table-fixed [&_table]:min-w-[1110px]`}
            footer={
              <DataTablePagination
                total={messagesQuery.data?.total ?? 0}
                page={page}
                pageSize={pageSize}
                onPageChange={setPage}
              />
            }
          />
        ) : null}
      </PageCard>
      <FormDialog open={createOpen} onOpenChange={updateCreateOpen} title="新建通知">
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            createMessage.mutate();
          }}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className={labelClass}>
              通知类型
              <select
                className={fieldClass}
                value={createForm.notification_type}
                onChange={(event) => updateCreateForm("notification_type", event.target.value)}
              >
                <option value="general">普通通知</option>
                <option value="system">系统通知</option>
                <option value="due">到期提醒</option>
                <option value="overdue">逾期提醒</option>
                <option value="reservation">预约通知</option>
                <option value="task">任务提醒</option>
              </select>
            </label>
            <label className={labelClass}>
              处理方式
              <select
                className={fieldClass}
                value={createForm.mode}
                onChange={(event) => updateCreateForm("mode", event.target.value as NotificationFormState["mode"])}
              >
                <option value="draft">保存草稿</option>
                <option value="send">立即发送</option>
              </select>
            </label>
          </div>
          <label className={labelClass}>
            标题
            <input
              className={fieldClass}
              value={createForm.title}
              onChange={(event) => updateCreateForm("title", event.target.value)}
              placeholder="输入通知标题"
            />
          </label>
          <label className={labelClass}>
            内容
            <textarea
              className="min-h-[112px] w-full resize-none rounded-[10px] border border-[#dce4f2] bg-white px-3 py-2 text-sm font-semibold leading-6 text-[#101a35] outline-none focus:border-[var(--bf-brand)]"
              value={createForm.content}
              onChange={(event) => updateCreateForm("content", event.target.value)}
              placeholder="输入通知内容"
            />
          </label>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className={labelClass}>
              接收范围
              <select
                className={fieldClass}
                value={createForm.target_type}
                onChange={(event) => updateTargetType(event.target.value as NotificationTargetType)}
              >
                <option value="all_readers">全体读者</option>
                <option value="all_admins">全体管理员</option>
                <option value="all">全体读者和管理员</option>
                <option value="reader">指定读者</option>
                <option value="admin">指定管理员</option>
              </select>
            </label>
            {["reader", "admin"].includes(createForm.target_type) ? (
              <div className={`${labelClass} md:col-span-2`}>
                {createForm.target_type === "reader" ? "指定读者" : "指定管理员"}
                <RecipientPicker
                  targetType={recipientType}
                  values={createForm.recipient_ids}
                  keyword={recipientKeyword}
                  items={recipientQuery.data?.items ?? []}
                  loading={recipientQuery.isLoading}
                  error={recipientQuery.isError}
                  fieldClass={fieldClass}
                  onKeywordChange={setRecipientKeyword}
                  onValuesChange={(value) => updateCreateForm("recipient_ids", value)}
                />
              </div>
            ) : (
              <div className="rounded-[10px] border border-[#e8eef6] bg-[#f8fbff] px-4 py-3 text-sm font-bold text-[#64718d]">
                {createForm.mode === "draft" ? "草稿会预生成投递记录，但接收方在发送后才可见。" : "立即发送会创建投递记录并标记为已发送。"}
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <ActionButton type="button" variant="secondary" onClick={() => updateCreateOpen(false)}>
              取消
            </ActionButton>
            <ActionButton type="submit" disabled={createMessage.isPending}>
              {createMessage.isPending ? "处理中" : createForm.mode === "draft" ? "保存草稿" : "立即发送"}
            </ActionButton>
          </div>
        </form>
      </FormDialog>
      <FormDialog open={Boolean(selectedMessage)} onOpenChange={(open) => !open && setSelectedMessage(null)} title="通知详情">
        {selectedMessage ? (
          <div className="grid gap-4">
            <div className="rounded-[14px] border border-[#e8eef6] bg-[#fbfcff] p-4">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge value={formatNotificationType(selectedMessage.notification_type)} tone={selectedMessage.notification_type === "reservation" ? "purple" : "blue"} />
                <StatusBadge value={lifecycleStatusView(String(selectedMessage.lifecycle_status ?? "")).label} tone={lifecycleStatusView(String(selectedMessage.lifecycle_status ?? "")).tone} />
                <span className="text-xs font-bold text-[#64718d]">{String(selectedMessage.message_code ?? "")}</span>
              </div>
              <h3 className="mt-4 text-lg font-black text-[#101a35]">{formatNotificationTitle(selectedMessage)}</h3>
              <p className="mt-3 whitespace-pre-wrap text-sm font-semibold leading-7 text-[#31405f]">{String(selectedMessage.content ?? "暂无内容")}</p>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-2">
              <div className="rounded-[12px] bg-[#f8fbff] p-3">
                <div className="text-xs font-black text-[#31405f]">接收范围</div>
                <div className="mt-1 font-bold text-[#101a35]">{formatScope(selectedMessage)}</div>
              </div>
              <div className="rounded-[12px] bg-[#f8fbff] p-3">
                <div className="text-xs font-black text-[#31405f]">投递统计</div>
                <div className="mt-1 font-bold text-[#101a35]">
                  {formatNumber(selectedMessage.sent_deliveries)} / {formatNumber(selectedMessage.total_deliveries)} 已投
                  {Number(selectedMessage.failed_deliveries ?? 0) > 0 ? `，失败 ${formatNumber(selectedMessage.failed_deliveries)}` : ""}
                </div>
              </div>
              <div className="rounded-[12px] bg-[#f8fbff] p-3">
                <div className="text-xs font-black text-[#31405f]">创建人</div>
                <div className="mt-1 font-bold text-[#101a35]">{String(selectedMessage.created_by_code ?? "-")}</div>
              </div>
              <div className="rounded-[12px] bg-[#f8fbff] p-3">
                <div className="text-xs font-black text-[#31405f]">更新时间</div>
                <div className="mt-1 font-bold text-[#101a35]">{formatDateTime(selectedMessage.updated_at ?? selectedMessage.created_at)}</div>
              </div>
            </div>
            <div className="flex justify-end">
              <ActionButton variant="secondary" onClick={() => setSelectedMessage(null)}>关闭</ActionButton>
            </div>
          </div>
        ) : null}
      </FormDialog>
    </div>
  );
}
