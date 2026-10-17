import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { analyticsApi } from "@/api/analytics";
import { tasksApi } from "@/api/tasks";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { DataTable, DataTablePagination, type DataColumn } from "@/components/ui/DataTable";
import { FormDialog } from "@/components/ui/FormDialog";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageCard } from "@/components/ui/PageCard";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";
import { asArray, formatDateTime, formatNumber } from "@/utils/format";
import {
  formatAIAction,
  formatAIReason,
  formatAIToolName,
  formatDataFieldLabel,
  formatDataFieldValue,
  formatHandlerType,
  formatPriority,
  formatQueueName,
  formatRiskLevel,
  formatSecondaryText,
  formatServiceType,
  formatSourceType,
  formatTaskTitle,
} from "@/utils/labels";
import { labelForStatus } from "@/utils/status";
import rhythm from "@/styles/AdminRhythm.module.css";

type TaskTab = "all" | "high" | "reader_ops" | "exception" | "collection" | "notification";

const taskTabs: Array<{ key: TaskTab; label: string }> = [
  { key: "all", label: "全部任务" },
  { key: "high", label: "高优先级" },
  { key: "reader_ops", label: "读者/流通" },
  { key: "exception", label: "待人工/异常" },
  { key: "collection", label: "馆藏/排架" },
  { key: "notification", label: "通知任务" },
];

function asRecord(value: unknown): AnyRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as AnyRecord) : {};
}

function text(value: unknown, fallback = "-") {
  const content = String(value ?? "").trim();
  return content || fallback;
}

function taskParams(tab: TaskTab): AnyRecord {
  if (tab === "high") return { priority: "high" };
  if (tab === "exception") return { status: "waiting_human" };
  if (tab === "reader_ops") return { task_group: "reader_ops" };
  if (tab === "collection") return { task_group: "catalog" };
  if (tab === "notification") return { task_group: "notification" };
  return {};
}

function canTakeover(row: AnyRecord) {
  return ["pending", "ai_processing", "waiting_human", "claimed"].includes(String(row.status ?? ""));
}

function canResolve(row: AnyRecord) {
  return ["admin_processing", "waiting_human", "claimed"].includes(String(row.status ?? ""));
}

function DetailItem({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-[8px] border border-[#e7edf7] bg-[#f8fbff] px-3 py-2">
      <div className="text-[11px] font-black uppercase tracking-[0.04em] text-[#64718d]">{label}</div>
      <div className="mt-1 break-words text-[13px] font-bold leading-5 text-[#10203f]">{text(value)}</div>
    </div>
  );
}

function serviceTypeLabel(value: unknown) {
  return formatServiceType(value);
}

function serviceStatusLabel(value: unknown) {
  return labelForStatus(value);
}

function serviceResultText(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "-";
  const row = value as AnyRecord;
  const fields = ["loan_id", "reservation_id", "renewal_id", "status", "due_at", "new_due_at", "returned_at", "copy_status"];
  return fields
    .filter((key) => row[key] !== undefined && row[key] !== null && row[key] !== "")
    .map((key) => `${formatDataFieldLabel(key)}：${formatDataFieldValue(key, row[key])}`)
    .join("，") || "-";
}

function ServiceRequestSummary({ request, onOpen }: { request: AnyRecord; onOpen: (request: AnyRecord) => void }) {
  const requestType = String(request.request_type ?? "");
  const status = String(request.status ?? "");
  const canOpen = status === "ready" && ["borrow", "return"].includes(requestType);
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[13px] font-black text-[#10203f]">流通服务请求</div>
        {canOpen ? (
          <ActionButton size="sm" variant={requestType === "return" ? "warning" : "primary"} onClick={() => onOpen(request)}>
            去办理
          </ActionButton>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <DetailItem label="类型" value={serviceTypeLabel(request.request_type)} />
        <DetailItem label="状态" value={serviceStatusLabel(request.status)} />
        <DetailItem label="请求码" value={request.request_code} />
        <DetailItem label="凭证码" value={request.voucher_code} />
        <DetailItem label="读者" value={request.reader_code} />
        <DetailItem label="图书/副本" value={[request.book_code, request.copy_code].filter(Boolean).join(" / ")} />
        <DetailItem label="借阅/预约" value={[request.loan_code, request.reservation_code].filter(Boolean).join(" / ")} />
        <DetailItem label="AI 结果" value={serviceResultText(request.result)} />
      </div>
      {!canOpen && status !== "completed" ? (
        <div className="rounded-[8px] border border-[#e7edf7] bg-[#f8fbff] px-3 py-2 text-[12px] font-bold text-[#64718d]">
          当前请求不能直接办理；可先接管任务，再按详情中的读者、图书或借阅记录到对应业务页处理。
        </div>
      ) : null}
    </section>
  );
}

function AITraceSummary({ task }: { task: AnyRecord }) {
  const plan = asRecord(task.ai_plan);
  const trace = asRecord(task.ai_trace);
  const outcome = asRecord(trace.outcome);
  const toolResults = asArray<AnyRecord>(trace.tool_results);
  const followupResults = asArray<AnyRecord>(trace.followup_results);
  const hasAI = Boolean(task.ai_run_id || Object.keys(plan).length || Object.keys(trace).length);

  if (!hasAI) {
    return (
      <div className="rounded-[8px] border border-dashed border-[#d8e1f0] bg-white px-4 py-3 text-sm font-bold text-[#64718d]">
        AI 尚未处理该任务，普管可接管处理。
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <DetailItem label="AI 状态" value={labelForStatus(trace.status ?? task.status)} />
        <DetailItem label="SOP/计划" value={formatAIAction(plan.sop_id ?? plan.action ?? "autonomous_decision")} />
        <DetailItem label="处理结论" value={formatAIReason(outcome.reason ?? task.interrupt_reason ?? task.ai_error ?? trace.status)} />
        <DetailItem label="后续动作" value={outcome.next_action ? formatAIAction(outcome.next_action) : `后续步骤 ${outcome.followup_steps ?? followupResults.length}`} />
      </div>
      {toolResults.length ? (
        <div className="rounded-[8px] border border-[#e7edf7] bg-white">
          <div className="border-b border-[#edf1f7] px-3 py-2 text-[12px] font-black text-[#31405f]">AI 执行步骤</div>
          <div className="divide-y divide-[#edf1f7]">
            {toolResults.slice(0, 6).map((item, index) => (
              <div key={`${text(item.tool_name)}-${index}`} className="px-3 py-2 text-[12px] font-semibold text-[#47516b]">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-black text-[#10203f]">{formatAIToolName(item.tool_name)}</span>
                  <span>{labelForStatus(item.status)}</span>
                </div>
                {item.reason ? <div className="mt-1 text-[#64718d]">{formatAIReason(item.reason)}</div> : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function TasksPage() {
  const [tab, setTab] = useState<TaskTab>("all");
  const [page, setPage] = useState(1);
  const [selectedTaskCode, setSelectedTaskCode] = useState("");
  const pageSize = 8;
  const admin = useAuthStore((state) => state.admin);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const params = taskParams(tab);

  const taskStats = useQuery({ queryKey: ["analytics", "tasks"], queryFn: analyticsApi.tasks });
  const taskQuery = useQuery({
    queryKey: ["tasks", params, page, pageSize],
    queryFn: () => tasksApi.list({ ...params, limit: pageSize, offset: (page - 1) * pageSize }),
  });
  const detailQuery = useQuery({
    queryKey: ["tasks", "detail", selectedTaskCode],
    queryFn: () => tasksApi.detail(selectedTaskCode),
    enabled: Boolean(selectedTaskCode),
  });

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["tasks"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics", "tasks"] }),
    ]);
  };
  const claimMutation = useMutation({
    mutationFn: (taskCode: string) => tasksApi.claim(taskCode, { admin_code: admin?.admin_code }),
    onSuccess: async () => {
      toast.success("任务已接管");
      await invalidate();
    },
  });
  const resolveMutation = useMutation({
    mutationFn: (taskCode: string) => tasksApi.resolve(taskCode, { resolution: "resolved" }),
    onSuccess: async () => {
      toast.success("任务已完成");
      await invalidate();
    },
  });

  if (taskQuery.isError || taskStats.isError) return <ErrorState onRetry={() => void Promise.all([taskQuery.refetch(), taskStats.refetch()])} />;

  const rows = taskQuery.data?.items ?? [];
  const stats = taskStats.data ?? {};
  const detail = detailQuery.data ?? rows.find((row) => String(row.task_code) === selectedTaskCode) ?? null;
  const serviceRequest = asRecord((detail as AnyRecord | null)?.service_request);
  const hasTableContent = taskQuery.isLoading || taskStats.isLoading || rows.length > 0;
  const statCards = [
    { title: "任务池总量", value: formatNumber(taskQuery.data?.total ?? 0), unit: "条", icon: "data", tone: "blue" as const },
    { title: "AI 处理中", value: formatNumber(stats.ai_processing_count ?? stats.ai_pending_task_count ?? 0), unit: "条", icon: "ai", tone: "purple" as const },
    { title: "待人工介入", value: formatNumber(stats.exception_count ?? 0), unit: "条", icon: "risk", tone: "red" as const },
    { title: "今日完成", value: formatNumber(stats.today_completed ?? 0), unit: "条", icon: "success", tone: "green" as const },
  ];

  const columns: DataColumn<AnyRecord>[] = [
    {
      key: "type",
      title: "来源",
      width: "88px",
      render: (row) => <FeatureIcon name={row.source_type === "ai_admin" ? "ai" : "data"} tone={row.priority === "urgent" || row.priority === "high" ? "red" : "blue"} size="sm" />,
    },
    {
      key: "content",
      title: "任务内容",
      render: (row) => (
        <div>
          <div className="font-bold text-[#101a35]">{formatTaskTitle(row)}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--bf-text-secondary)]">
            <span className="rounded bg-[#f3f6fb] px-2 py-0.5">{formatSourceType(row.source_type)}</span>
            <span className="rounded bg-[#f3f6fb] px-2 py-0.5">{formatQueueName(row.queue_name)}</span>
            <span className="max-w-[520px] truncate">{formatSecondaryText(row.description ?? row.task_code)}</span>
          </div>
        </div>
      ),
    },
    { key: "created", title: "进入任务池", width: "135px", render: (row) => <span className="text-[var(--bf-text-secondary)]">{formatDateTime(row.created_at)}</span> },
    { key: "priority", title: "优先级", width: "92px", align: "center", render: (row) => <StatusBadge value={row.priority} /> },
    { key: "status", title: "状态", width: "110px", align: "center", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      title: "操作",
      width: "170px",
      align: "center",
      render: (row) => (
        <div className="flex justify-center gap-2">
          {canTakeover(row) ? (
            <ActionButton size="sm" variant="secondary" onClick={() => claimMutation.mutate(String(row.task_code))} disabled={claimMutation.isPending}>
              接管
            </ActionButton>
          ) : null}
          {canResolve(row) ? (
            <ActionButton size="sm" onClick={() => resolveMutation.mutate(String(row.task_code))} disabled={resolveMutation.isPending}>
              完成
            </ActionButton>
          ) : null}
          <ActionButton size="sm" variant="ghost" onClick={() => setSelectedTaskCode(String(row.task_code))}>
            详情
          </ActionButton>
        </div>
      ),
    },
  ];

  const openServiceRequest = (request: AnyRecord) => {
    const code = encodeURIComponent(String(request.request_code ?? request.voucher_code ?? ""));
    if (!code) return;
    if (request.request_type === "borrow") navigate(`/admin/borrowing/borrow?service_code=${code}`);
    if (request.request_type === "return") navigate(`/admin/borrowing/return?service_code=${code}`);
  };

  return (
    <div className={rhythm.compactPage}>
      <div className="flex items-end justify-between gap-4">
        <div />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} compact className="h-[108px] min-h-[108px] px-5" />
        ))}
      </div>
      <PageCard className={`${rhythm.pagedCard} ${hasTableContent ? rhythm.tasksCard : rhythm.emptyTableCard}`} bodyClassName={rhythm.pagedBody}>
        <div className="flex flex-wrap items-center gap-3 border-b border-[var(--bf-border-soft)] px-5 py-2">
          {taskTabs.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => {
                setTab(item.key);
                setPage(1);
              }}
              className={`h-9 rounded-xl px-5 text-sm font-black transition ${
                tab === item.key ? "bg-[#eeeaff] text-[var(--bf-brand)] shadow-sm" : "bg-[#f8faff] text-[#1b2848] hover:bg-[#f0f4ff]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        {hasTableContent ? (
          <DataTable
            rows={rows}
            columns={columns}
            loading={taskQuery.isLoading || taskStats.isLoading}
            emptyTitle="暂无任务"
            emptyMode="none"
            className={`${rhythm.pagedTable} ${rhythm.tasksTable}`}
            footer={<DataTablePagination total={taskQuery.data?.total ?? 0} page={page} pageSize={pageSize} onPageChange={setPage} />}
          />
        ) : null}
      </PageCard>
      <FormDialog open={Boolean(selectedTaskCode)} onOpenChange={(open) => !open && setSelectedTaskCode("")} title="任务详情">
        {detail ? (
          <div className="space-y-4 text-sm font-semibold text-[#31405f]">
            <section className="space-y-2">
              <div className="text-[13px] font-black text-[#10203f]">任务状态</div>
              <div className="grid grid-cols-2 gap-2">
                <DetailItem label="任务编号" value={detail.task_code} />
                <DetailItem label="状态" value={labelForStatus(detail.status)} />
                <DetailItem label="优先级" value={formatPriority(detail.priority)} />
                <DetailItem label="风险" value={formatRiskLevel(detail.risk_level)} />
                <DetailItem label="队列" value={formatQueueName(detail.queue_name)} />
                <DetailItem label="执行方" value={formatHandlerType(detail.handler_type)} />
              </div>
              <DetailItem label="任务内容" value={formatTaskTitle(detail)} />
              <DetailItem label="说明" value={detail.description} />
            </section>
            <section className="space-y-2">
              <div className="text-[13px] font-black text-[#10203f]">AI 处理记录</div>
              <AITraceSummary task={detail} />
            </section>
            {Object.keys(serviceRequest).length ? <ServiceRequestSummary request={serviceRequest} onOpen={openServiceRequest} /> : null}
            <section className="space-y-2">
              <div className="text-[13px] font-black text-[#10203f]">人工接管</div>
              <div className="grid grid-cols-2 gap-2">
                <DetailItem label="转人工原因" value={formatAIReason(detail.interrupt_reason || detail.ai_error)} />
                <DetailItem label="接管人" value={detail.claimed_by_code || detail.takeover_by_code} />
                <DetailItem label="接管时间" value={formatDateTime(detail.takeover_at || detail.claimed_at)} />
                <DetailItem label="完成时间" value={formatDateTime(detail.resolved_at)} />
              </div>
            </section>
          </div>
        ) : (
          <div className="rounded-[8px] border border-[#e7edf7] bg-[#f8fbff] px-4 py-3 text-sm font-bold text-[#64718d]">正在加载任务详情...</div>
        )}
      </FormDialog>
    </div>
  );
}
