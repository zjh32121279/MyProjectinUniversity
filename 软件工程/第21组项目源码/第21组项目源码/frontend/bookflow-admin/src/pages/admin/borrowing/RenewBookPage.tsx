import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { circulationApi } from "@/api/circulation";
import { readersApi } from "@/api/readers";
import { rulesApi } from "@/api/rules";
import {
  BorrowingStepLayout,
  OperationResultPanel,
  OperationSummaryPanel,
  ReaderSearchPanel,
  renewSteps,
} from "@/components/borrowing/BorrowingShared";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";
import { formatDateTime, formatNumber } from "@/utils/format";

function value(row: AnyRecord | null | undefined, key: string, fallback = "—") {
  const raw = row?.[key];
  if (raw === undefined || raw === null || raw === "") return fallback;
  return String(raw);
}

function RenewableLoansPanel({ reader, selected, onSelect }: { reader: AnyRecord | null; selected: AnyRecord | null; onSelect: (row: AnyRecord) => void }) {
  const query = useQuery({
    queryKey: ["borrow-records", "renewable", reader?.id],
    queryFn: () => circulationApi.loans({ reader_id: Number(reader?.id), status: "renewable", limit: 100, offset: 0 }),
    enabled: Boolean(reader?.id),
  });
  const rows = query.data?.items ?? [];
  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-[18px] border border-[var(--bf-border-soft)] bg-white p-4">
      <div className="shrink-0">
        <h3 className="text-[17px] font-black leading-6 text-[#071334]">选择在借记录</h3>
        <p className="mt-1 text-xs leading-5 text-[var(--bf-text-secondary)]">续借必须基于现有借阅记录，不能重新选择可借副本。</p>
      </div>
      <div className="mt-4 min-h-0 flex-1 overflow-y-auto overflow-x-hidden pr-1 bf-scrollbar">
        {!reader ? <EmptyState title="请先选择读者" /> : null}
        {reader && query.isLoading ? <div className="rounded-[16px] bg-[#f8fafc] p-5 text-sm font-bold text-[var(--bf-text-secondary)]">正在加载该读者的在借记录...</div> : null}
        <div className="space-y-3">
          {rows.map((loan) => {
            const active = selected?.loan_id === loan.loan_id;
            return (
              <button
                key={String(loan.loan_id)}
                type="button"
                onClick={() => onSelect(loan)}
                className={`w-full rounded-2xl border p-4 text-left transition hover:bg-[#fbfdff] ${active ? "border-[var(--bf-brand)] bg-[#eef4ff]" : "border-[var(--bf-border-soft)] bg-white"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-[15px] font-black text-[#101a35]">{value(loan, "title")}</div>
                    <div className="mt-1 text-xs font-bold text-[var(--bf-text-secondary)]">{value(loan, "copy_code")} / {value(loan, "book_code")}</div>
                  </div>
                  <StatusBadge value={loan.status} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-bold text-[var(--bf-text-secondary)]">
                  <span>借出：{formatDateTime(loan.borrowed_at)}</span>
                  <span>应还：{formatDateTime(loan.due_at)}</span>
                  <span>续借次数：{formatNumber(loan.renewal_count)}</span>
                  <span>逾期天数：{formatNumber(loan.overdue_days)}</span>
                </div>
              </button>
            );
          })}
        </div>
        {reader && !query.isLoading && !rows.length ? <EmptyState title="该读者暂无可续借记录" /> : null}
      </div>
    </section>
  );
}

export function RenewBookPage() {
  const [readerKeyword, setReaderKeyword] = useState("");
  const [selectedReader, setSelectedReader] = useState<AnyRecord | null>(null);
  const [selectedLoan, setSelectedLoan] = useState<AnyRecord | null>(null);
  const [result, setResult] = useState<AnyRecord | null>(null);
  const admin = useAuthStore((state) => state.admin);
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const prefillMode = searchParams.get("prefill") === "1";

  const operationState = useQuery({
    queryKey: ["operation-state", "renew"],
    queryFn: () => circulationApi.borrowingState({ mode: "renew" }),
    enabled: prefillMode && !selectedReader,
  });

  useEffect(() => {
    if (operationState.data?.reader_code && !selectedReader) {
      readersApi.list({ keyword: operationState.data.reader_code as string, limit: 1 }).then((res) => {
        const reader = res?.items?.[0];
        if (reader) setSelectedReader(reader as AnyRecord);
      });
    }
  }, [operationState.data, selectedReader]);

  useEffect(() => {
    setSelectedLoan(null);
    setResult(null);
  }, [selectedReader?.id]);

  const activity = useQuery({ queryKey: ["reader-activity", selectedReader?.reader_code], queryFn: () => readersApi.activity(String(selectedReader?.reader_code)), enabled: Boolean(selectedReader?.reader_code) });
  const rules = useQuery({ queryKey: ["rules", "borrow"], queryFn: rulesApi.borrow });

  const rule = useMemo(() => {
    return (rules.data?.items ?? []).find((item) => item.reader_type_code === selectedReader?.reader_type_code && item.circulation_type === selectedLoan?.circulation_type);
  }, [rules.data?.items, selectedLoan?.circulation_type, selectedReader?.reader_type_code]);

  const activeCount = Number(activity.data?.active_borrow_count ?? 0);
  const maxRenewals = Number(rule?.max_renewals ?? 0);
  const renewalCount = Number(selectedLoan?.renewal_count ?? 0);
  const readerBlocked = Boolean(selectedReader?.borrow_suspended || selectedReader?.status !== "active");
  const renewBlocked = Boolean(selectedLoan && maxRenewals >= 0 && renewalCount >= maxRenewals);
  const canSubmit = Boolean(selectedReader && selectedLoan && !readerBlocked && !renewBlocked);

  const mutation = useMutation({
    mutationFn: () => circulationApi.renew({ loan_id: Number(selectedLoan?.loan_id) }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["borrow-records"] });
      queryClient.invalidateQueries({ queryKey: ["reader-activity"] });
    },
  });

  const current = result ? 2 : selectedLoan ? 1 : 0;

  return (
    <BorrowingStepLayout title="办理续借" description="按读者当前借阅记录办理续借，避免把续借误处理为重新借书。" steps={renewSteps} current={current} tone="green">
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_280px]">
          <ReaderSearchPanel
            keyword={readerKeyword}
            onKeywordChange={setReaderKeyword}
            selected={selectedReader}
            onSelect={setSelectedReader}
            onClear={() => setSelectedReader(null)}
          />
          <RenewableLoansPanel reader={selectedReader} selected={selectedLoan} onSelect={setSelectedLoan} />
          <OperationSummaryPanel
            title="续借详情"
            items={[
              { label: "读者", value: selectedReader ? `${String(selectedReader.name)} / ${String(selectedReader.reader_code)}` : "尚未选择读者" },
              { label: "借阅记录", value: selectedLoan ? `#${String(selectedLoan.loan_id)} / ${String(selectedLoan.copy_code ?? "-")}` : "尚未选择在借记录" },
              { label: "图书", value: selectedLoan ? `${String(selectedLoan.title ?? "-")} / ${String(selectedLoan.book_code ?? "-")}` : "—" },
              { label: "原应还日期", value: selectedLoan ? formatDateTime(selectedLoan.due_at) : "—" },
              { label: "续借次数", value: selectedLoan ? `${renewalCount} / ${maxRenewals}` : "—", tone: renewBlocked ? "danger" : selectedLoan ? "success" : "normal" },
              { label: "当前状态", value: selectedLoan ? <StatusBadge value={selectedLoan.status} /> : "—" },
              { label: "信用分", value: selectedReader ? String(formatNumber(selectedReader.credit_score)) : "—" },
              { label: "是否满足条件", value: canSubmit ? "满足续借条件" : !selectedReader || !selectedLoan ? "等待选择" : readerBlocked ? "读者受限" : renewBlocked ? "已达续借上限" : "不满足条件", tone: canSubmit ? "success" : "normal" },
            ]}
          >
            {result ? (
              <OperationResultPanel
                items={[
                  { label: "续借记录", value: String(result.renewal_id ?? "-") },
                  { label: "原应还日期", value: String(result.old_due_at ?? "-") },
                  { label: "新应还日期", value: String(result.new_due_at ?? "-") },
                ]}
                onReset={() => {
                  setSelectedLoan(null);
                  setResult(null);
                }}
              />
            ) : null}
          </OperationSummaryPanel>
        </div>
        <div className="mt-4 flex shrink-0 items-center justify-between gap-4 rounded-[18px] border border-[#c7f0d8] bg-[#f4fdf7] px-4 py-3">
          <div className="flex min-w-0 items-center gap-2 truncate text-sm font-bold text-[#075c2f]">
            <FeatureIcon name="success" tone="green" size="sm" />
            <span className="truncate">
              {selectedLoan && rule ? `规则：${String(selectedReader?.reader_type_code ?? "-")} / ${String(selectedLoan.circulation_type ?? "-")}，每次续借延长 ${String(rule.borrow_days ?? "-")} 天，最多续借 ${String(rule.max_renewals ?? "-")} 次。` : `当前馆员：${String(admin?.name ?? admin?.admin_code ?? "-")}。选择读者和在借记录后，系统会按借阅规则办理续借。`}
            </span>
          </div>
          <ActionButton size="lg" variant="success" disabled={!canSubmit || mutation.isPending || Boolean(result)} onClick={() => mutation.mutate()}>
            确认续借
          </ActionButton>
        </div>
      </div>
    </BorrowingStepLayout>
  );
}
