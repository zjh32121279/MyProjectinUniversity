import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { catalogApi } from "@/api/catalog";
import { circulationApi } from "@/api/circulation";
import { readersApi } from "@/api/readers";
import { rulesApi } from "@/api/rules";
import {
  BorrowingStepLayout,
  CopySearchPanel,
  OperationResultPanel,
  OperationSummaryPanel,
  ReaderSearchPanel,
  borrowSteps,
} from "@/components/borrowing/BorrowingShared";
import { ActionButton } from "@/components/ui/ActionButton";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";
import { formatNumber } from "@/utils/format";

export function BorrowBookPage() {
  const [readerKeyword, setReaderKeyword] = useState("");
  const [copyKeyword, setCopyKeyword] = useState("");
  const [selectedReader, setSelectedReader] = useState<AnyRecord | null>(null);
  const [selectedCopy, setSelectedCopy] = useState<AnyRecord | null>(null);
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
    queryKey: ["operation-state", "borrow"],
    queryFn: () => circulationApi.borrowingState({ mode: "borrow" }),
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
    if (operationState.data?.copy_code && selectedReader && !selectedCopy) {
      catalogApi.copies({ keyword: operationState.data.copy_code as string, limit: 1 }).then((res) => {
        const copy = res?.items?.[0];
        if (copy) setSelectedCopy(copy as AnyRecord);
      });
    }
  }, [operationState.data, selectedReader, selectedCopy]);

  const activity = useQuery({ queryKey: ["reader-activity", selectedReader?.reader_code], queryFn: () => readersApi.activity(String(selectedReader?.reader_code)), enabled: Boolean(selectedReader?.reader_code) });
  const rules = useQuery({ queryKey: ["rules", "borrow"], queryFn: rulesApi.borrow });

  const rule = useMemo(() => {
    return (rules.data?.items ?? []).find((item) => item.reader_type_code === selectedReader?.reader_type_code && item.circulation_type === selectedCopy?.circulation_type);
  }, [rules.data?.items, selectedCopy?.circulation_type, selectedReader?.reader_type_code]);

  const activeCount = Number(activity.data?.active_borrow_count ?? 0);
  const maxBorrowCount = Number(rule?.max_borrow_count ?? selectedReader?.max_borrow_count ?? 8);
  const copyAvailable = selectedCopy?.copy_status === "available";
  const serviceRequestReady = serviceRequest?.request_type === "borrow" && serviceRequest?.status === "ready";
  const serviceRequestBlocked = Boolean(serviceRequest && !serviceRequestReady);
  const serviceCopyMatched = Boolean(serviceRequestReady && selectedCopy?.copy_code && serviceRequest?.copy_code && String(selectedCopy.copy_code) === String(serviceRequest.copy_code));
  const readerBlocked = Boolean(selectedReader?.borrow_suspended || selectedReader?.status !== "active");
  const limitBlocked = Boolean(activeCount >= maxBorrowCount);
  const canSubmit = Boolean(selectedReader && selectedCopy && (copyAvailable || serviceCopyMatched) && !readerBlocked && !limitBlocked && !serviceRequestBlocked);

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
      if (row.request_type !== "borrow") {
        setServiceRequest(null);
        setServiceMessage(`该任务是 ${String(row.request_type ?? "-")} 类型，不能用于借书确认。`);
        return;
      }
      const readerCode = String(row.reader_code ?? "");
      const copyCode = String(row.copy_code ?? "");
      setServiceRequest(row);
      setResult(null);
      setReaderKeyword(readerCode);
      setCopyKeyword(copyCode);
      if (readerCode) {
        const readers = await readersApi.list({ keyword: readerCode, limit: 1 });
        setSelectedReader((readers?.items?.[0] as AnyRecord | undefined) ?? null);
      }
      if (copyCode) {
        const copies = await catalogApi.copies({ keyword: copyCode, limit: 1 });
        setSelectedCopy((copies?.items?.[0] as AnyRecord | undefined) ?? null);
      }
      setServiceMessage(row.status === "ready" ? "已读取借书任务，可核对后确认。" : `该借书任务当前状态为 ${String(row.status ?? "-")}。`);
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
        return circulationApi.completeBorrowRequest(requestCode);
      }
      return circulationApi.borrow({ reader_code: String(selectedReader?.reader_code), copy_code: String(selectedCopy?.copy_code) });
    },
    onSuccess: (data) => {
      const requestResult = data?.result && typeof data.result === "object" ? (data.result as AnyRecord) : null;
      setResult(requestResult ? { ...requestResult, request_code: data.request_code, status: requestResult.status ?? "active" } : data);
      if (data?.request_type === "borrow") {
        setServiceRequest(data);
      }
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["copies"] });
      queryClient.invalidateQueries({ queryKey: ["borrow-records"] });
      queryClient.invalidateQueries({ queryKey: ["reader-activity"] });
    },
  });

  const current = result ? 3 : selectedReader && selectedCopy ? 2 : selectedReader ? 1 : 0;

  return (
    <BorrowingStepLayout title="办理借书" description="为读者办理图书借出，自动校验信用、借阅上限和副本状态。" steps={borrowSteps} current={current} tone="blue">
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="mb-3 flex shrink-0 flex-wrap items-center gap-3 rounded-[18px] border border-[#e5edf7] bg-white px-4 py-3">
          <div className="text-sm font-black text-[#071334]">任务/凭证码</div>
          <input
            className="h-10 min-w-[220px] flex-1 rounded-[var(--bf-radius-control)] border border-[#d7e3f7] bg-white px-3 text-sm font-bold text-[#1b2848] outline-none placeholder:font-normal placeholder:text-[var(--bf-text-secondary)]"
            value={serviceCode}
            onChange={(event) => {
              setServiceCode(event.target.value);
              setServiceMessage("");
            }}
            placeholder="输入 AI 生成的借书任务码或凭证码"
          />
          <ActionButton variant="secondary" onClick={() => void loadServiceRequest()}>读取任务</ActionButton>
          {serviceMessage ? <div className="min-w-[220px] flex-1 truncate text-sm font-semibold text-[var(--bf-text-secondary)]">{serviceMessage}</div> : null}
        </div>
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_280px]">
          <ReaderSearchPanel
            keyword={readerKeyword}
            onKeywordChange={(value) => {
              setReaderKeyword(value);
              setServiceRequest(null);
            }}
            selected={selectedReader}
            onSelect={(value) => {
              setSelectedReader(value);
              setServiceRequest(null);
            }}
            onClear={() => {
              setSelectedReader(null);
              setServiceRequest(null);
            }}
          />
          <CopySearchPanel
            keyword={copyKeyword}
            onKeywordChange={(value) => {
              setCopyKeyword(value);
              setServiceRequest(null);
            }}
            selected={selectedCopy}
            onSelect={(value) => {
              setSelectedCopy(value);
              setServiceRequest(null);
            }}
            onClear={() => {
              setSelectedCopy(null);
              setServiceRequest(null);
            }}
            status={serviceRequestReady ? undefined : "available"}
          />
          <OperationSummaryPanel
            title="校验结果"
            items={[
              { label: "读者", value: selectedReader ? `${String(selectedReader.name)} / ${String(selectedReader.reader_code)}` : "尚未选择读者", tone: selectedReader ? (readerBlocked ? "danger" : "success") : "normal" },
              { label: "读者类型", value: selectedReader ? String(selectedReader.reader_type_code ?? "-") : "等待选择读者" },
              { label: "信用分", value: selectedReader ? String(formatNumber(selectedReader.credit_score)) : "等待选择读者", tone: selectedReader && Number(selectedReader.credit_score) >= 80 ? "success" : selectedReader ? "danger" : "normal" },
              { label: "在借 / 上限", value: selectedReader ? `${activeCount} / ${maxBorrowCount}` : "等待选择读者", tone: limitBlocked ? "danger" : selectedReader ? "success" : "normal" },
              { label: "副本", value: selectedCopy ? `${String(selectedCopy.title)} / ${String(selectedCopy.copy_code)}` : "尚未选择副本" },
              { label: "副本状态", value: selectedCopy ? (copyAvailable ? "在馆可借" : serviceCopyMatched ? "AI 任务锁定" : "不可借") : "尚未选择副本", tone: selectedCopy && !copyAvailable && !serviceCopyMatched ? "danger" : selectedCopy ? "success" : "normal" },
              { label: "借阅规则", value: rule ? `借期 ${String(rule.borrow_days ?? "-")} 天，最多续借 ${String(rule.max_renewals ?? "-")} 次` : selectedReader && selectedCopy ? "未匹配规则" : "等待选择" },
            ]}
          >
            {canSubmit ? (
              <div className="rounded-2xl border border-[#c7f0d8] bg-[#f4fdf7] p-3 text-sm font-bold text-[#075c2f]">校验通过，可办理借出</div>
            ) : null}
            {mutation.isError ? (
              <div className="mt-3 rounded-xl border border-[#fdd] bg-[#fff5f5] p-3 text-sm font-bold text-[var(--bf-danger)]">借出失败：{String((mutation.error as any)?.message ?? "未知错误")}</div>
            ) : null}
            {result ? (
              <OperationResultPanel
                items={[
                  { label: "借阅记录", value: String(result.loan_id ?? "-") },
                  { label: "应还日期", value: String(result.due_at ?? "-") },
                  { label: "状态", value: String(result.status ?? "-") },
                ]}
                onReset={() => {
                  setSelectedCopy(null);
                  setResult(null);
                }}
              />
            ) : null}
          </OperationSummaryPanel>
        </div>
        <div className="mt-4 flex shrink-0 items-center justify-between gap-4 rounded-[18px] border border-[#e5edf7] bg-[#f8fbff] px-4 py-3">
          <ActionButton variant="secondary" onClick={() => { setSelectedReader(null); setSelectedCopy(null); setResult(null); setServiceRequest(null); setServiceCode(""); setServiceMessage(""); }}>清空</ActionButton>
          <div className="min-w-0 flex-1 truncate text-sm font-semibold text-[var(--bf-text-secondary)]">
            {canSubmit ? (serviceRequestReady ? "AI 借书任务已核对，可确认办理。" : "校验通过：可确认借出。") : "请先选择读者和在馆可借副本，系统会自动校验借阅规则。"}
          </div>
          <ActionButton size="lg" disabled={!canSubmit || mutation.isPending || Boolean(result)} onClick={() => mutation.mutate()}>
            确认借出
          </ActionButton>
        </div>
      </div>
    </BorrowingStepLayout>
  );
}
