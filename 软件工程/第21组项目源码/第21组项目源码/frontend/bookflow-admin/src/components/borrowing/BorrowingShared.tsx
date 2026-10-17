import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/api/dashboard";
import { catalogApi } from "@/api/catalog";
import { circulationApi } from "@/api/circulation";
import { readersApi } from "@/api/readers";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { BookPlaceholder } from "@/components/ui/BookPlaceholder";
import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SearchInput } from "@/components/ui/SearchInput";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StepProgress } from "@/components/ui/StepProgress";
import type { AnyRecord } from "@/types/api";
import { asArray, formatDateTime, formatNumber } from "@/utils/format";
import type { Tone } from "@/utils/status";
import rhythm from "@/styles/AdminRhythm.module.css";

export const borrowSteps = ["读者检索", "副本检索", "校验结果", "确认借出"];
export const returnSteps = ["扫描副本编号", "确认借阅记录", "还书结果"];
export const renewSteps = ["读者检索", "选择在借记录", "确认续借"];
export const reservationSteps = ["读者检索", "预约信息", "预约校验", "处理结果"];

function str(value: unknown, fallback = "—") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function firstValue(row: AnyRecord | null | undefined, keys: string[], fallback = "—") {
  if (!row) return fallback;
  for (const key of keys) {
    const value = row[key];
    if (value !== undefined && value !== null && value !== "") return String(value);
  }
  return fallback;
}

function Panel({ title, subtitle, children, className }: { title: string; subtitle?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-[18px] border border-[var(--bf-border-soft)] bg-white p-4 ${className ?? ""}`}>
      <div className="shrink-0">
        <h3 className="text-[17px] font-black leading-6 text-[#071334]">{title}</h3>
        {subtitle ? <p className="mt-1 text-xs leading-5 text-[var(--bf-text-secondary)]">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ScrollArea({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`min-h-0 overflow-y-auto overflow-x-hidden pr-1 bf-scrollbar ${className}`}>{children}</div>;
}

function DetailRow({ label, value, tone }: { label: string; value: ReactNode; tone?: "success" | "danger" | "warning" }) {
  return (
    <div className="rounded-xl bg-[#f8fbff] px-3 py-2.5">
      <div className="text-xs font-bold text-[#071334]">{label}</div>
      <div className={tone === "success" ? "mt-1 text-sm font-bold text-[var(--bf-success)]" : tone === "danger" ? "mt-1 text-sm font-bold text-[var(--bf-danger)]" : tone === "warning" ? "mt-1 text-sm font-bold text-[var(--bf-warning)]" : "mt-1 text-sm text-[var(--bf-text-secondary)]"}>{value}</div>
    </div>
  );
}

function ReaderDetailCard({ reader }: { reader: AnyRecord }) {
  return (
    <div className="rounded-2xl border border-[#dce8ff] bg-gradient-to-br from-[#f9fbff] to-white p-4 shadow-[0_10px_24px_rgba(31,68,135,0.04)]">
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#eaf1ff] text-lg font-black text-[var(--bf-brand)]">
          {str(reader.name, "读").slice(0, 1)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[17px] font-black text-[#071334]">{str(reader.name)}</div>
          <div className="mt-1 text-xs font-semibold text-[var(--bf-text-secondary)]">{str(reader.reader_code)} · {str(reader.reader_type_code)}</div>
        </div>
        <StatusBadge value={reader.borrow_suspended ? "受限" : reader.status ?? "active"} tone={reader.borrow_suspended ? "orange" : "green"} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <DetailRow label="信用分" value={formatNumber(reader.credit_score)} tone={Number(reader.credit_score ?? 0) >= 80 ? "success" : "warning"} />
        <DetailRow label="当前在借" value={formatNumber(reader.active_borrow_count ?? reader.borrow_count ?? 0)} />
        <DetailRow label="最大可借" value={formatNumber(reader.max_borrow_count ?? 8)} />
        <DetailRow label="预约数量" value={formatNumber(reader.active_reservation_count ?? reader.reservation_count ?? 0)} />
      </div>
      <div className="mt-3 rounded-xl bg-[#fbfcff] p-3 text-xs leading-5 text-[var(--bf-text-secondary)]">
        到期提醒：到期前 3 天<br />逾期提醒：第 1 / 7 / 15 天
      </div>
    </div>
  );
}

function CopyDetailCard({ copy }: { copy: AnyRecord }) {
  const location = firstValue(copy, ["shelf_position", "position_code", "location_name", "zone_name"]);
  return (
    <div className="rounded-2xl border border-[#dce8ff] bg-gradient-to-br from-[#f9fbff] to-white p-4">
      <div className="flex gap-3">
        <BookPlaceholder title={str(copy.title)} code={str(copy.book_code)} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[17px] font-black text-[#071334]">{str(copy.title)}</div>
          <div className="mt-1 text-xs text-[var(--bf-text-secondary)]">{str(copy.author)} · {str(copy.publisher)}</div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs font-bold">
            <span className="rounded-lg bg-[#eef4ff] px-2 py-1 text-[var(--bf-brand)]">{str(copy.book_code)}</span>
            <span className="rounded-lg bg-[#f4f7fb] px-2 py-1 text-[#516079]">{str(copy.copy_code)}</span>
          </div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <DetailRow label="状态" value={<StatusBadge value={copy.status} />} />
        <DetailRow label="馆藏位置" value={location} />
        <DetailRow label="流通类型" value={str(copy.circulation_type)} />
        <DetailRow label="出版年" value={str(copy.publish_year)} />
      </div>
    </div>
  );
}

export function BorrowingStats() {
  const dashboard = useQuery({ queryKey: ["dashboard", "borrowing"], queryFn: dashboardApi.admin });
  if (dashboard.isError) return <ErrorState onRetry={() => dashboard.refetch()} />;
  const data = dashboard.data;
  const cards = [
    { title: "今日借出", value: formatNumber(data?.today_borrow_count), unit: "册", icon: "borrow", tone: "blue" as Tone },
    { title: "今日归还", value: formatNumber(data?.today_return_count), unit: "册", icon: "return", tone: "green" as Tone },
    { title: "今日到期", value: formatNumber(data?.due_today_count), unit: "册", icon: "data", tone: "orange" as Tone },
    { title: "当前预约", value: formatNumber(data?.reservation_count), unit: "条", icon: "reservation", tone: "purple" as Tone },
  ];
  return (
    <div className="grid h-full grid-cols-4 gap-4">
      {cards.map((card) => <StatCard key={card.title} {...card} compact />)}
    </div>
  );
}

export function BorrowingModeCard({ title, description, icon, tone, to }: { title: string; description: string; icon: string; tone: Tone; to: string }) {
  return (
    <Link to={to} className="bf-card flex min-h-[430px] h-full min-w-0 flex-col bg-white px-7 pb-7 pt-8 text-left transition hover:-translate-y-0.5 hover:border-[#d7e3f7] hover:shadow-[0_16px_30px_rgba(15,23,42,0.055)]">
      <FeatureIcon name={icon} tone={tone} size="xl" />
      <div className="mt-7 text-[23px] font-black text-[#071334]">{title}</div>
      <div className="mt-4 max-w-[230px] text-[15px] leading-7 text-[var(--bf-text-secondary)]">{description}</div>
      <span className="mt-auto inline-flex h-[48px] w-full items-center justify-center gap-2 self-center rounded-[var(--bf-radius-control)] bg-[var(--bf-brand)] text-[15px] font-black text-white">进入办理 →</span>
    </Link>
  );
}

export function BorrowingStepLayout({ title, description, steps, current, tone, children }: { title: string; description: string; steps: string[]; current: number; tone: "blue" | "green" | "orange" | "purple"; children: ReactNode }) {
  return (
    <div className={`${rhythm.borrowStepLayout} flex min-h-0 flex-col overflow-hidden rounded-[18px] border border-[#e8edf6] bg-white p-5 shadow-[0_16px_38px_rgba(15,23,42,0.055)]`}>
      <div className="flex h-[46px] shrink-0 items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-[20px] font-bold leading-6 text-[#071334]">{title}</h2>
          <p className="mt-1 truncate text-xs text-[var(--bf-text-secondary)]">{description}</p>
        </div>
        <Link
          to="/admin/borrowing"
          className="inline-flex h-9 shrink-0 items-center gap-2 rounded-[var(--bf-radius-control)] border border-[#dce4f2] bg-white px-3 text-sm font-bold text-[#1b2848] transition hover:bg-[#f7faff]"
        >
          <span className="text-base leading-none">←</span>
          返回首页
        </Link>
      </div>
      <div className="mt-2 h-[58px] shrink-0 overflow-hidden">
        <StepProgress steps={steps} current={current} tone={tone} />
      </div>
      <div className="mt-4 min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}

export function ReaderSearchPanel({ keyword, onKeywordChange, selected, onSelect, onClear }: { keyword: string; onKeywordChange: (value: string) => void; selected?: AnyRecord | null; onSelect: (row: AnyRecord) => void; onClear?: () => void }) {
  const query = useQuery({ queryKey: ["readers", "borrowing", keyword], queryFn: () => readersApi.list({ keyword: keyword || undefined, limit: 8 }) });
  return (
    <Panel title="读者检索">
      <SearchInput className="mt-4 h-[42px]" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="读者编号 / 姓名 / 手机号" />
      <div className="mt-4 min-h-0 flex-1 overflow-hidden">
        {selected ? (
          <div className="space-y-3">
            <button type="button" onClick={onClear} className="block w-full rounded-2xl text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_26px_rgba(31,68,135,0.08)]">
              <ReaderDetailCard reader={selected} />
            </button>
            {onClear ? <ActionButton className="w-full" size="sm" variant="secondary" onClick={onClear}>重新选择读者</ActionButton> : null}
          </div>
        ) : (
          <ScrollArea className="max-h-[380px] space-y-3">
            {(query.data?.items ?? []).map((reader) => (
              <button key={String(reader.reader_code)} type="button" onClick={() => onSelect(reader)} className="w-full rounded-xl border border-[var(--bf-border-soft)] p-4 text-left hover:bg-[#fbfdff]">
                <div className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate font-bold text-[#101a35]">{str(reader.name)}</span>
                  <StatusBadge value={reader.borrow_suspended ? "受限" : reader.status} tone={reader.borrow_suspended ? "orange" : "green"} />
                </div>
                <div className="mt-2 text-xs text-[var(--bf-text-secondary)]">{str(reader.reader_code)} / 信用分 {formatNumber(reader.credit_score)}</div>
              </button>
            ))}
          </ScrollArea>
        )}
        {!query.isLoading && !selected && !(query.data?.items ?? []).length ? <EmptyState title="暂无读者记录" /> : null}
      </div>
    </Panel>
  );
}

export function CopySearchPanel({ keyword, onKeywordChange, selected, onSelect, onClear, status }: { keyword: string; onKeywordChange: (value: string) => void; selected?: AnyRecord | null; onSelect: (row: AnyRecord) => void; onClear?: () => void; status?: string }) {
  const query = useQuery({ queryKey: ["copies", "borrowing", keyword, status], queryFn: () => catalogApi.copies({ keyword: keyword || undefined, status, limit: 8 }) });
  const rows = asArray<AnyRecord>(query.data?.items).filter((row) => row.copy_code !== selected?.copy_code).slice(0, 6);
  return (
    <Panel title="副本检索">
      <SearchInput className="mt-4 h-[42px]" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="扫描或输入副本编号 / 条码号" />
      <div className="mt-4 min-h-0 flex-1 overflow-hidden">
        {selected ? (
          <div className="space-y-3">
            <button type="button" onClick={onClear} className="block w-full rounded-2xl text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_26px_rgba(31,68,135,0.08)]">
              <CopyDetailCard copy={selected} />
            </button>
            {onClear ? <ActionButton className="w-full" size="sm" variant="secondary" onClick={onClear}>重新选择副本</ActionButton> : null}
          </div>
        ) : null}
        <ScrollArea className={`${selected ? "mt-4 max-h-[210px]" : "max-h-[370px]"} space-y-2`}>
          {rows.map((row) => (
            <button key={String(row.copy_code)} type="button" onClick={() => onSelect(row)} className="flex w-full items-center gap-3 rounded-xl border border-[var(--bf-border-soft)] p-3 text-left hover:bg-[#fbfdff]">
              <BookPlaceholder title={str(row.title)} code={str(row.book_code)} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-black text-[#101a35]">{str(row.title)}</span>
                <span className="mt-1 block truncate text-xs text-[var(--bf-text-secondary)]">{str(row.copy_code)} / {str(row.book_code)}</span>
              </span>
              <StatusBadge value={row.copy_status} />
            </button>
          ))}
        </ScrollArea>
        {!query.isLoading && !selected && !rows.length ? <EmptyState title="暂无副本记录" /> : null}
      </div>
    </Panel>
  );
}

export function BookSearchPanel({ keyword, onKeywordChange, selected, onSelect, onClear }: { keyword: string; onKeywordChange: (value: string) => void; selected?: AnyRecord | null; onSelect: (row: AnyRecord) => void; onClear?: () => void }) {
  const query = useQuery({ queryKey: ["books", "borrowing", keyword], queryFn: () => catalogApi.books({ keyword: keyword || undefined, limit: 8 }) });
  return (
    <Panel title="图书检索">
      <SearchInput className="mt-4" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="输入书名 / 图书编号" />
      <ScrollArea className="mt-4 max-h-[360px] space-y-3">
        {(query.data?.items ?? []).map((book) => (
          <button key={String(book.book_code)} type="button" onClick={() => selected?.book_code === book.book_code && onClear ? onClear() : onSelect(book)} className={`flex w-full min-w-0 items-center gap-3 rounded-xl border p-4 text-left hover:bg-[#fbfdff] ${selected?.book_code === book.book_code ? "border-[var(--bf-brand)] bg-[#eef4ff]" : "border-[var(--bf-border-soft)]"}`}>
            <BookPlaceholder title={str(book.title)} code={str(book.book_code)} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-bold text-[#101a35]">{str(book.title)}</span>
              <span className="mt-1 block text-xs text-[var(--bf-text-secondary)]">{str(book.book_code)} / 可借 {formatNumber(book.available_copies)} 册</span>
            </span>
            <StatusBadge value={book.circulation_type} />
          </button>
        ))}
      </ScrollArea>
      {!query.isLoading && !(query.data?.items ?? []).length ? <EmptyState title="暂无图书记录" /> : null}
    </Panel>
  );
}

export function LoanPanel({ keyword, onKeywordChange, selected, onSelect, activeOnly = false, placeholder = "输入读者 / 图书 / 副本关键字", highlightTone = "success" }: { keyword: string; onKeywordChange: (value: string) => void; selected?: AnyRecord | null; onSelect: (row: AnyRecord) => void; activeOnly?: boolean; placeholder?: string; highlightTone?: "success" | "warning" | "danger" }) {
  const query = useQuery({ queryKey: ["borrow-records", "borrowing", keyword, activeOnly], queryFn: () => circulationApi.loans({ keyword: keyword || undefined, status: undefined, limit: 6 }) });
  const rows = asArray<AnyRecord>(query.data?.items).slice(0, 5);
  const columns: DataColumn<AnyRecord>[] = [
    { key: "reader", title: "读者", width: "96px", render: (row) => <span className="font-bold">{firstValue(row, ["reader_name", "name"])}<br /><span className="text-xs font-normal text-[var(--bf-text-secondary)]">{str(row.reader_code)}</span></span> },
    { key: "book", title: "图书", width: "145px", render: (row) => <span className="font-bold">{firstValue(row, ["title", "book_title"])}<br /><span className="text-xs font-normal text-[var(--bf-text-secondary)]">{str(row.copy_code)}</span></span> },
    { key: "due_at", title: "应还日期", width: "96px", nowrap: true, render: (row) => <span className="whitespace-nowrap">{str(row.due_at)}</span> },
    { key: "status", title: "状态", width: "68px", align: "center", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", title: "操作", width: "66px", align: "center", render: (row) => <ActionButton className="h-8 px-2.5" size="sm" variant={selected?.loan_id === row.loan_id ? "primary" : "secondary"} onClick={() => onSelect(row)}>选择</ActionButton> },
  ];
  return (
    <Panel title="借阅记录" subtitle="扫描副本后确认当前借阅信息。">
      <SearchInput className="mt-4 h-[42px]" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder={placeholder} />
      {selected ? (
        <div className="mt-4 shrink-0 rounded-2xl border border-[#dce8ff] bg-[#fbfcff] p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailRow label="读者" value={`${firstValue(selected, ["reader_name", "name"])} / ${str(selected.reader_code)}`} />
            <DetailRow label="副本编号" value={str(selected.copy_code)} tone={highlightTone} />
            <DetailRow label="借出日期" value={str(selected.borrowed_at)} />
            <DetailRow label="应还日期" value={str(selected.due_at)} />
          </div>
        </div>
      ) : null}
      <div className="mt-4 min-h-0 flex-1 overflow-auto pr-1 bf-scrollbar">
        <DataTable className="[&_table]:min-w-[500px] [&_td]:px-1.5 [&_th]:px-1.5" rows={rows} columns={columns} loading={query.isLoading} emptyTitle="暂无借阅记录" />
      </div>
    </Panel>
  );
}

export function ReservationRecordPanel({ keyword, onKeywordChange, status, onStatusChange, actions, readerId, onSelectRequest, selectedRequestCode }: { keyword: string; onKeywordChange: (value: string) => void; status: string; onStatusChange: (value: string) => void; actions: (row: AnyRecord) => ReactNode; readerId?: number | null; onSelectRequest?: (row: AnyRecord) => void; selectedRequestCode?: string | null }) {
  const query = useQuery({ queryKey: ["pending-requests", "borrowing", keyword, status, String(readerId ?? "")], queryFn: () => circulationApi.pendingRequests({ keyword: keyword || undefined, status: status || undefined, reader_id: readerId ?? undefined, limit: 8 }) });
  const columns: DataColumn<AnyRecord>[] = [
    { key: "book", title: "书名/读者", render: (row) => <span className="font-bold">{str((row.book as AnyRecord | undefined)?.title)}<br /><span className="text-xs font-normal text-[var(--bf-text-secondary)]">{str((row.reader as AnyRecord | undefined)?.name)}</span></span> },
    { key: "created", title: "预约时间", width: "126px", nowrap: true, render: (row) => formatDateTime(row.created_at).slice(0, 16) },
    { key: "status", title: "状态", width: "76px", align: "center", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", title: "操作", width: "104px", align: "center", render: actions },
  ];
  return (
    <Panel title="预约信息（待处理）">
      <div className="mt-4 flex shrink-0 flex-col gap-3 lg:flex-row">
        <SearchInput className="min-w-0 flex-1" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="搜索预约、读者或图书" />
        <select className="bf-control w-full px-3 text-sm font-semibold text-[#1b2848] lg:w-[140px]" value={status} onChange={(event) => onStatusChange(event.target.value)}>
          <option value="">全部状态</option>
          <option value="ready">待处理</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
          <option value="expired">已过期</option>
        </select>
      </div>
      <div className="mt-4 min-h-0 flex-1 overflow-auto pr-1 bf-scrollbar">
        <DataTable className="[&_table]:min-w-[590px] [&_td]:px-1.5 [&_th]:px-1.5" rows={asArray<AnyRecord>(query.data?.items).slice(0, 6)} columns={columns} loading={query.isLoading} emptyTitle="暂无待处理的借阅请求" onRowClick={(row) => onSelectRequest?.(row)} />
      </div>
    </Panel>
  );
}

export function OperationSummaryPanel({ title = "校验与确认", items, children }: { title?: string; items: { label: string; value: ReactNode; tone?: "normal" | "danger" | "success" | "warning" }[]; children?: ReactNode }) {
  return (
    <Panel title={title}>
      <ScrollArea className="mt-4 flex-1 space-y-3">
        {items.map((item) => (
          <DetailRow key={item.label} label={item.label} value={item.value} tone={item.tone === "normal" ? undefined : item.tone} />
        ))}
      </ScrollArea>
      {children ? <div className="mt-4 shrink-0">{children}</div> : null}
    </Panel>
  );
}

export function OperationResultPanel({ title = "完成反馈", items, onReset }: { title?: string; items: { label: string; value: ReactNode }[]; onReset?: () => void }) {
  return (
    <div className="rounded-2xl border border-[#c7f0d8] bg-[#f4fdf7] p-4">
      <div className="flex items-center gap-3">
        <FeatureIcon name="success" tone="green" size="sm" />
        <h3 className="text-lg font-black text-[#075c2f]">{title}</h3>
      </div>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        {items.map((item) => <DetailRow key={item.label} label={item.label} value={item.value} />)}
      </div>
      {onReset ? <ActionButton className="mt-4" variant="secondary" icon="refresh" onClick={onReset}>继续办理</ActionButton> : null}
    </div>
  );
}

export function AvailableCopiesPanel({ keyword, onKeywordChange, selected, onSelect }: { keyword: string; onKeywordChange: (value: string) => void; selected?: AnyRecord | null; onSelect: (row: AnyRecord) => void }) {
  const query = useQuery({ queryKey: ["copies", "available", keyword], queryFn: () => catalogApi.copies({ keyword: keyword || undefined, status: "available", limit: 6 }) });
  const rows = asArray<AnyRecord>(query.data?.items).slice(0, 5);
  return (
    <Panel title="可借的图书（在馆可借）">
      <SearchInput className="mt-4 h-[42px]" value={keyword} onChange={(event) => onKeywordChange(event.target.value)} placeholder="书名 / 副本编号" />
      <ScrollArea className="mt-4 flex-1 space-y-2">
        {rows.map((row) => (
          <button key={String(row.copy_code)} type="button" onClick={() => onSelect(row)} className={`grid w-full grid-cols-[42px_minmax(0,1fr)_74px] items-center gap-3 rounded-xl border p-3 text-left transition hover:bg-[#fbfdff] ${selected?.copy_code === row.copy_code ? "border-[var(--bf-success)] bg-[#f4fdf7] ring-1 ring-[var(--bf-success)]" : "border-[var(--bf-border-soft)] bg-white"}`}>
            <BookPlaceholder title={str(row.title)} code={str(row.book_code)} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-black text-[#101a35]">{str(row.title)}</span>
              <span className="mt-1 block truncate text-xs text-[var(--bf-text-secondary)]">{str(row.copy_code)} / {str(row.book_code)}</span>
            </span>
            <span className="inline-flex h-7 w-[68px] shrink-0 items-center justify-center justify-self-center rounded-lg bg-[#eef4ff] px-2 text-center text-xs font-black text-[var(--bf-brand)]">选择</span>
          </button>
        ))}
        {!query.isLoading && !rows.length ? <EmptyState title="暂无在馆可借副本" /> : null}
      </ScrollArea>
    </Panel>
  );
}
