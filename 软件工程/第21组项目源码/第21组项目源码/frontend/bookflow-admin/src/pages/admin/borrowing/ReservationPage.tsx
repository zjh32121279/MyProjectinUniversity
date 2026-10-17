import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { circulationApi } from "@/api/circulation";
import { readersApi } from "@/api/readers";
import {
  BookSearchPanel,
  BorrowingStepLayout,
  OperationResultPanel,
  OperationSummaryPanel,
  ReaderSearchPanel,
  ReservationRecordPanel,
  reservationSteps,
} from "@/components/borrowing/BorrowingShared";
import { ActionButton } from "@/components/ui/ActionButton";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";
import { formatNumber } from "@/utils/format";

export function ReservationPage() {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<"create" | "records">(searchParams.get("tab") === "create" ? "create" : "records");
  const [readerKeyword, setReaderKeyword] = useState("");
  const [bookKeyword, setBookKeyword] = useState("");
  const [recordKeyword, setRecordKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [selectedReader, setSelectedReader] = useState<AnyRecord | null>(null);
  const [selectedBook, setSelectedBook] = useState<AnyRecord | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<AnyRecord | null>(null);
  const [voucherCode, setVoucherCode] = useState("");
  const [voucherError, setVoucherError] = useState("");
  const [result, setResult] = useState<AnyRecord | null>(null);
  const admin = useAuthStore((state) => state.admin);
  const queryClient = useQueryClient();
  const prefillMode = searchParams.get("prefill") === "1";

  const operationState = useQuery({
    queryKey: ["operation-state", "reservation"],
    queryFn: () => circulationApi.borrowingState({ mode: "reservation" }),
    enabled: prefillMode && !selectedReader,
  });

  useEffect(() => {
    if (operationState.data?.reader_code && !selectedReader) {
      setTab("records");
      readersApi.list({ keyword: operationState.data.reader_code as string, limit: 1 }).then((res) => {
        const reader = res?.items?.[0];
        if (reader) setSelectedReader(reader as AnyRecord);
      });
    }
  }, [operationState.data, selectedReader]);

  const createReservation = useMutation({
    mutationFn: () => circulationApi.createReservation({ reader_code: String(selectedReader?.reader_code), book_code: String(selectedBook?.book_code) }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const cancelRequest = useMutation({
    mutationFn: (requestCode: string) => circulationApi.cancelRequest(requestCode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const completeBorrow = useMutation({
    mutationFn: ({ requestCode, voucherCode }: { requestCode: string; voucherCode: string }) => circulationApi.completeBorrowRequest(requestCode, voucherCode),
    onSuccess: (data) => {
      setResult(data as AnyRecord);
      setVoucherError("");
      setSelectedRequest(null);
      queryClient.invalidateQueries({ queryKey: ["pending-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail || error?.message || "";
      if (detail.includes("Voucher code") || detail.includes("凭证")) {
        setVoucherError("凭证号验证失败：" + detail);
      } else {
        setVoucherError("借出操作失败，请检查请求是否仍然有效。");
      }
    },
  });

  const handleSelectRequest = (row: AnyRecord) => {
    setSelectedRequest(row);
    setVoucherError("");
  };

  const handleVoucherChange = (value: string) => {
    setVoucherCode(value);
    setVoucherError("");
  };

  const handleCancelRequest = (requestCode: string) => {
    if (window.confirm("确认取消该借阅请求？取消后副本将被释放。")) cancelRequest.mutate(requestCode);
  };

  const handleProcessReservation = () => {
    const trimmed = voucherCode.trim();
    if (!trimmed) {
      setVoucherError("请输入读者提供的凭证号。");
      return;
    }
    if (!selectedRequest) {
      setVoucherError("请先在预约信息列表中选中一条记录。");
      return;
    }
    if (selectedRequest.status !== "ready") {
      setVoucherError("该请求状态不是待处理，无法执行借出操作。");
      return;
    }
    completeBorrow.mutate({ requestCode: String(selectedRequest.request_code), voucherCode: trimmed });
  };

  const current = result ? 3 : tab === "records" && selectedReader ? 2 : selectedReader && selectedBook ? 2 : selectedReader ? 1 : 0;

  return (
    <BorrowingStepLayout title="预约处理" description="创建预约、查看预约保留并完成预约履约。" steps={reservationSteps} current={current} tone="purple">
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="mb-3 flex shrink-0 gap-2">
          <button type="button" className={`h-9 rounded-[var(--bf-radius-control)] px-4 text-sm font-bold ${tab === "create" ? "bg-[var(--bf-ai)] text-white" : "border border-[#dce4f2] bg-white text-[#1b2848]"}`} onClick={() => setTab("create")}>
            新建预约
          </button>
          <button type="button" className={`h-9 rounded-[var(--bf-radius-control)] px-4 text-sm font-bold ${tab === "records" ? "bg-[var(--bf-ai)] text-white" : "border border-[#dce4f2] bg-white text-[#1b2848]"}`} onClick={() => setTab("records")}>
            预约记录处理
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          {tab === "create" ? (
            <div className="grid h-full grid-cols-1 gap-4 overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_280px]">
              <ReaderSearchPanel keyword={readerKeyword} onKeywordChange={setReaderKeyword} selected={selectedReader} onSelect={setSelectedReader} onClear={() => setSelectedReader(null)} />
              <BookSearchPanel keyword={bookKeyword} onKeywordChange={setBookKeyword} selected={selectedBook} onSelect={setSelectedBook} onClear={() => setSelectedBook(null)} />
              <OperationSummaryPanel
                title="预约校验"
                items={[
                  { label: "读者", value: selectedReader ? `${String(selectedReader.name)} / ${String(selectedReader.reader_code)}` : "尚未选择读者", tone: selectedReader ? "success" : "normal" },
                  { label: "读者状态", value: selectedReader ? (selectedReader.borrow_suspended ? "受限" : "正常") : "等待选择", tone: selectedReader?.borrow_suspended ? "danger" : "success" },
                  { label: "图书", value: selectedBook ? `${String(selectedBook.title)} / ${String(selectedBook.book_code)}` : "尚未选择图书" },
                  { label: "可借副本", value: selectedBook ? `${formatNumber(selectedBook.available_copies)} 册` : "等待选择图书", tone: selectedBook && Number(selectedBook.available_copies) > 0 ? "success" : "normal" },
                  { label: "信用分", value: selectedReader ? String(formatNumber(selectedReader.credit_score)) : "—", tone: selectedReader && Number(selectedReader.credit_score) >= 80 ? "success" : "normal" },
                ]}
              >
                {selectedReader && selectedBook ? (
                  <div className="rounded-xl border border-[#c7f0d8] bg-[#f4fdf7] p-3 font-black text-[#075c2f]">校验通过，可创建预约</div>
                ) : null}
                {result ? (
                  <OperationResultPanel
                    items={[
                      { label: "预约编号", value: String(result.reservation_id ?? "-") },
                      { label: "状态", value: String(result.status ?? "-") },
                      { label: "保留副本", value: String(result.fulfilled_copy_id ?? "-") },
                    ]}
                    onReset={() => {
                      setSelectedBook(null);
                      setResult(null);
                    }}
                  />
                ) : null}
              </OperationSummaryPanel>
            </div>
          ) : (
            <div className="grid h-full grid-cols-1 gap-4 overflow-hidden xl:grid-cols-[280px_minmax(0,1fr)_280px]">
              <ReaderSearchPanel keyword={readerKeyword} onKeywordChange={setReaderKeyword} selected={selectedReader} onSelect={(reader) => { setSelectedReader(reader); setSelectedRequest(null); setVoucherCode(""); setVoucherError(""); }} onClear={() => { setSelectedReader(null); setSelectedRequest(null); setVoucherCode(""); setVoucherError(""); }} />
              <ReservationRecordPanel
                keyword={recordKeyword}
                onKeywordChange={setRecordKeyword}
                status={status}
                onStatusChange={setStatus}
                readerId={selectedReader?.id as number | undefined}
                selectedRequestCode={selectedRequest?.request_code as string | undefined}
                onSelectRequest={handleSelectRequest}
                actions={(row) => (
                  <div className="flex justify-end gap-2">
                    {row.status === "ready" ? (
                      <ActionButton size="sm" variant="secondary" disabled={cancelRequest.isPending} onClick={() => handleCancelRequest(String(row.request_code))}>
                        取消
                      </ActionButton>
                    ) : null}
                  </div>
                )}
              />
              <OperationSummaryPanel
                title="预约校验结果"
                items={[
                  { label: "读者状态", value: selectedReader ? (selectedReader.borrow_suspended ? "受限" : "正常") : "—", tone: selectedReader?.borrow_suspended ? "danger" : "success" },
                  { label: "信用分", value: selectedReader ? String(formatNumber(selectedReader.credit_score)) : "—", tone: selectedReader && Number(selectedReader.credit_score) >= 80 ? "success" : "normal" },
                  { label: "在借数", value: selectedReader ? String(formatNumber((selectedReader as any)?.active_borrow_count ?? 0)) : "—" },
                  { label: "选中记录", value: selectedRequest ? `${String((selectedRequest.book as AnyRecord)?.title ?? "—")} / ${String(selectedRequest.copy_code ?? "—")}` : "—", tone: selectedRequest ? "success" : "normal" },
                  { label: "请求状态", value: selectedRequest ? String(selectedRequest.status) : "—", tone: selectedRequest?.status === "ready" ? "success" : "normal" },
                ]}
              >
                {/* Voucher code input */}
                <div className="mt-3 space-y-2">
                  <label className="text-xs font-bold text-[#071334]">凭证号验证</label>
                  <input
                    type="text"
                    className="bf-control h-10 w-full rounded-[var(--bf-radius-control)] border border-[#dce4f2] px-3 text-sm font-semibold text-[#1b2848] placeholder:text-[#94a3b8]"
                    placeholder="输入读者出示的凭证号（如 BR99515792）"
                    value={voucherCode}
                    onChange={(e) => handleVoucherChange(e.target.value)}
                  />
                  {voucherError ? (
                    <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-3 py-2 text-xs font-bold text-[#dc2626]">{voucherError}</div>
                  ) : null}
                </div>
                {result ? (
                  <div className="mt-3">
                    <OperationResultPanel
                      items={[
                        { label: "借阅编号", value: String((result as any)?.loan_id ?? (result as any)?.data?.loan_id ?? "-") },
                        { label: "状态", value: String((result as any)?.status ?? (result as any)?.data?.status ?? "-") },
                        { label: "副本编号", value: String((result as any)?.copy_code ?? (result as any)?.data?.copy_code ?? "-") },
                      ]}
                      onReset={() => {
                        setSelectedRequest(null);
                        setVoucherCode("");
                        setVoucherError("");
                        setResult(null);
                      }}
                    />
                  </div>
                ) : null}
              </OperationSummaryPanel>
            </div>
          )}
        </div>
        <div className="mt-4 flex shrink-0 items-center justify-between gap-4 rounded-[18px] border border-[#e9ddff] bg-[#f7f2ff] px-4 py-3">
          <ActionButton variant="secondary" onClick={() => { setSelectedBook(null); setSelectedRequest(null); setVoucherCode(""); setVoucherError(""); setResult(null); }}>清空</ActionButton>
          <div className="min-w-0 flex-1 truncate text-sm font-bold text-[#5b3db8]">
            {tab === "records" ? "预约记录处理：输入凭证号并选中记录后点击处理预约。" : "新建预约：选择读者与图书后创建预约。"}
          </div>
          {tab === "create" ? (
            <ActionButton size="lg" variant="purple" disabled={!selectedReader || !selectedBook || createReservation.isPending} onClick={() => createReservation.mutate()}>
              确认预约
            </ActionButton>
          ) : (
            <ActionButton size="lg" variant="purple" disabled={completeBorrow.isPending} onClick={handleProcessReservation}>
              {completeBorrow.isPending ? "处理中…" : "处理预约"}
            </ActionButton>
          )}
        </div>
      </div>
    </BorrowingStepLayout>
  );
}
