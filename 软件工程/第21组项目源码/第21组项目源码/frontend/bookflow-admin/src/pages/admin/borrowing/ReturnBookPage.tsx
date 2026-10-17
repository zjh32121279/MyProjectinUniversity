import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { circulationApi } from "@/api/circulation";
import { LoanPanel, BorrowingStepLayout, OperationResultPanel, OperationSummaryPanel, returnSteps } from "@/components/borrowing/BorrowingShared";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { BookPlaceholder } from "@/components/ui/BookPlaceholder";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";

export function ReturnBookPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<AnyRecord | null>(null);
  const [result, setResult] = useState<AnyRecord | null>(null);
  const [serviceCode, setServiceCode] = useState("");
  const [serviceRequest, setServiceRequest] = useState<AnyRecord | null>(null);
  const [serviceMessage, setServiceMessage] = useState("");
  const admin = useAuthStore((state) => state.admin);
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const prefillMode = searchParams.get("prefill") === "1";
  const serviceCodeParam = searchParams.get("service_code") || searchParams.get("request_code") || searchParams.get("voucher_code") || "";

  const operationState = useQuery({
    queryKey: ["operation-state", "return"],
    queryFn: () => circulationApi.borrowingState({ mode: "return" }),
    enabled: prefillMode && !selectedRecord && !result,
  });

  const serviceRequestReady = serviceRequest?.request_type === "return" && serviceRequest?.status === "ready";
  const serviceRequestBlocked = Boolean(serviceRequest && !serviceRequestReady);

  const selectLoanByCopyCode = async (code: string) => {
    const res = await circulationApi.loans({ keyword: code, limit: 6 });
    const records = (res?.items ?? []) as AnyRecord[];
    const active = records.find((row) => row.status === "borrowed" || row.status === "overdue" || row.status === "active") ?? records[0];
    setKeyword(code);
    setSelectedRecord(active ?? null);
  };

  const loadServiceRequest = async (rawCode?: string) => {
    const code = String(rawCode ?? serviceCode).trim();
    if (!code) {
      setServiceMessage("请输入任务码或凭证码。");
      return;
    }
    if (rawCode !== undefined) {
      setServiceCode(code);
    }
    setServiceMessage("正在读取任务...");
    try {
      const row = await circulationApi.serviceRequest(code);
      if (row.request_type !== "return") {
        setServiceRequest(null);
        setServiceMessage(`该任务是 ${String(row.request_type ?? "-")} 类型，不能用于还书确认。`);
        return;
      }
      const copyCode = String(row.copy_code ?? "");
      setServiceRequest(row);
      setResult(null);
      if (copyCode) {
        await selectLoanByCopyCode(copyCode);
      } else {
        setSelectedRecord(null);
      }
      setServiceMessage(row.status === "ready" ? "已读取还书任务，可核对后确认。" : `该还书任务当前状态为 ${String(row.status ?? "-")}。`);
    } catch (error) {
      setServiceRequest(null);
      setServiceMessage(`读取失败：${String((error as any)?.message ?? "未知错误")}`);
    }
  };

  useEffect(() => {
    if (serviceCodeParam && !serviceCode && !serviceRequest) {
      void loadServiceRequest(serviceCodeParam);
    }
  }, [serviceCodeParam]);

  const mutation = useMutation({
    mutationFn: () => {
      if (serviceRequestReady) {
        const requestCode = String(serviceRequest?.request_code ?? serviceRequest?.voucher_code ?? serviceCode).trim();
        return circulationApi.completeReturnRequest(requestCode);
      }
      return circulationApi.returnCopy({ copy_code: String(selectedRecord?.copy_code ?? keyword) });
    },
    onSuccess: (data) => {
      const requestResult = data?.result && typeof data.result === "object" ? (data.result as AnyRecord) : null;
      setResult(requestResult ? { ...requestResult, request_code: data.request_code } : data);
      if (data?.request_type === "return") {
        setServiceRequest(data);
      }
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["borrow-records"] });
      queryClient.invalidateQueries({ queryKey: ["copies"] });
    },
  });

  useEffect(() => {
    if (operationState.data?.copy_code && !selectedRecord && !keyword) {
      const code = String(operationState.data.copy_code);
      circulationApi.loans({ keyword: code, limit: 6 }).then((res) => {
        const records = (res?.items ?? []) as AnyRecord[];
        const active = records.find((r) => r.status === "borrowed" || r.status === "overdue") ?? records[0];
        setKeyword(code);
        if (active) setSelectedRecord(active);
      });
    }
  }, [operationState.data, selectedRecord, keyword]);

  const overdueDays = Number(result?.overdue_days ?? selectedRecord?.overdue_days ?? 0);
  const current = result ? 2 : selectedRecord ? 1 : keyword ? 0 : 0;

  return (
    <BorrowingStepLayout title="办理还书" description="扫描或输入副本编号并办理归还，同步更新借阅记录和馆藏状态。" steps={returnSteps} current={current} tone="orange">
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="mb-3 flex shrink-0 flex-wrap items-center gap-3 rounded-[18px] border border-[#ffe0cc] bg-white px-4 py-3">
          <div className="text-sm font-black text-[#071334]">任务/凭证码</div>
          <input
            className="h-10 min-w-[220px] flex-1 rounded-[var(--bf-radius-control)] border border-[#ffd7b5] bg-white px-3 text-sm font-bold text-[#1b2848] outline-none placeholder:font-normal placeholder:text-[var(--bf-text-secondary)]"
            value={serviceCode}
            onChange={(event) => {
              setServiceCode(event.target.value);
              setServiceMessage("");
            }}
            placeholder="输入 AI 生成的还书任务码或凭证码"
          />
          <ActionButton variant="secondary" onClick={() => void loadServiceRequest()}>读取任务</ActionButton>
          {serviceMessage ? <div className="min-w-[220px] flex-1 truncate text-sm font-semibold text-[var(--bf-text-secondary)]">{serviceMessage}</div> : null}
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_280px]">
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-[18px] border border-[var(--bf-border-soft)] bg-white p-4">
            <div className="shrink-0">
              <h3 className="text-[17px] font-black text-[#071334]">扫描副本编号</h3>
              <p className="mt-1 text-xs text-[var(--bf-text-secondary)]">输入副本编号后自动匹配当前借阅记录。</p>
              <div className="mt-4 flex h-[42px] items-center rounded-[var(--bf-radius-control)] border border-[#d7e3f7] bg-white px-4 ring-2 ring-[#e4edff]">
                <span className="mr-2 text-lg font-bold text-[var(--bf-brand)]">#</span>
                <input
                  className="w-full border-none bg-transparent text-base font-bold text-[#1b2848] outline-none placeholder:text-sm placeholder:font-normal placeholder:text-[var(--bf-text-secondary)]"
                  value={keyword}
                  onChange={(event) => { setKeyword(event.target.value); setSelectedRecord(null); setResult(null); setServiceRequest(null); setServiceMessage(""); }}
                  placeholder="扫描或输入副本编号 / 条码"
                />
              </div>
            </div>
            <div className="mt-4 min-h-0 flex-1 overflow-y-auto pr-1 bf-scrollbar">
              {selectedRecord ? (
                <div className="rounded-2xl border border-[#dce8ff] bg-[#fbfcff] p-4">
                  <div className="flex gap-3">
                    <BookPlaceholder title={String(selectedRecord.title ?? "")} code={String(selectedRecord.book_code ?? "")} />
                    <div className="min-w-0">
                      <div className="truncate font-black text-[#071334]">{String(selectedRecord.title ?? "-")}</div>
                      <div className="mt-1 text-xs text-[var(--bf-text-secondary)]">副本：{String(selectedRecord.copy_code ?? keyword)}</div>
                      <div className="mt-1 text-xs text-[var(--bf-text-secondary)]">图书：{String(selectedRecord.book_code ?? "-")}</div>
                      <div className="mt-1 text-xs text-[var(--bf-text-secondary)]">状态：{String(selectedRecord.status ?? "-")}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl bg-[#f8fbff] p-4 text-sm text-[var(--bf-text-secondary)]">输入或扫描副本编号后，在中间区域确认借阅记录。</div>
              )}
            </div>
          </section>
          <LoanPanel
            keyword={keyword}
            onKeywordChange={(value) => {
              setKeyword(value);
              setServiceRequest(null);
              setServiceMessage("");
            }}
            selected={selectedRecord}
            onSelect={(value) => {
              setSelectedRecord(value);
              setServiceRequest(null);
              setServiceMessage("");
            }}
            activeOnly={!result}
            placeholder="输入读者 / 图书 / 副本关键字筛选借阅记录"
            highlightTone="warning"
          />
          <OperationSummaryPanel
            title={result ? "还书结果" : "归还确认"}
            items={[
              { label: "副本编号", value: selectedRecord ? String(selectedRecord.copy_code) : keyword || "等待扫描", tone: selectedRecord ? "warning" : "normal" },
              { label: "读者", value: selectedRecord ? `${String(selectedRecord.reader_name ?? "")} / ${String(selectedRecord.reader_code ?? "")}` : "等待匹配借阅记录" },
              { label: "借出日期", value: selectedRecord ? String(selectedRecord.borrowed_at ?? "-") : "—" },
              { label: "应还日期", value: selectedRecord ? String(selectedRecord.due_at ?? "-") : "—" },
              { label: "逾期情况", value: selectedRecord ? (overdueDays > 0 ? `已逾期 ${overdueDays} 天` : "未逾期") : "—", tone: overdueDays > 0 ? "danger" : selectedRecord ? "warning" : "normal" },
            ]}
          >
            {result ? (
              <OperationResultPanel
                title="归还完成"
                items={[
                  { label: "借阅记录", value: String(result.loan_id ?? "-") },
                  { label: "是否逾期", value: Number(result.overdue_days ?? 0) > 0 ? `是，${String(result.overdue_days)} 天` : "否" },
                  { label: "扣分", value: String(result.penalty_score ?? 0) },
                  { label: "副本新状态", value: String(result.copy_status ?? "-") },
                ]}
              />
            ) : null}
          </OperationSummaryPanel>
        </div>
        <div className="mt-4 flex shrink-0 items-center justify-between gap-4 rounded-[18px] border border-[#ffe0cc] bg-[#fff7ed] px-4 py-3">
          <div className="flex min-w-0 items-center gap-2 truncate text-sm font-bold text-[var(--bf-warning)]">
            <FeatureIcon name="risk" tone="orange" size="sm" />
            <span className="truncate">{selectedRecord ? (serviceRequestReady ? "AI 还书任务已核对，可确认办理。" : overdueDays > 0 ? `本次还书涉及逾期 ${overdueDays} 天，请确认扣分与副本状态。` : "未逾期，可正常办理归还。") : "请先扫描副本编号并确认借阅记录。"}</span>
          </div>
          <ActionButton size="lg" variant="warning" disabled={!selectedRecord || serviceRequestBlocked || mutation.isPending || Boolean(result)} onClick={() => mutation.mutate()}>
            确认还书
          </ActionButton>
        </div>
      </div>
    </BorrowingStepLayout>
  );
}
