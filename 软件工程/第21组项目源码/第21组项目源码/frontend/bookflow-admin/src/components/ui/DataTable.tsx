import type { CSSProperties, ReactNode } from "react";
import { EmptyState } from "@/components/ui/EmptyState";
import { TableSkeleton } from "@/components/ui/SkeletonBlock";
import { cn } from "@/utils/cn";

export type DataColumn<T> = {
  key: string;
  title: string;
  width?: string;
  align?: "left" | "center" | "right";
  nowrap?: boolean;
  render: (row: T, index: number) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataColumn<T>[];
  rows: T[];
  loading?: boolean;
  emptyTitle?: string;
  emptyMode?: "state" | "none";
  footer?: ReactNode;
  className?: string;
  onRowClick?: (row: T, index: number) => void;
};

function shouldNowrap(key: string, explicit?: boolean) {
  if (explicit !== undefined) return explicit;
  return /(code|status|priority|action|type|copy|date|time)/i.test(key);
}

export function DataTable<T>({ columns, rows, loading, emptyTitle, emptyMode = "state", footer, className, onRowClick }: DataTableProps<T>) {
  if (loading) return <TableSkeleton />;
  if (!rows.length) return emptyMode === "none" ? null : <EmptyState title={emptyTitle} />;

  const tableStyle = { "--bf-table-row-count": Math.max(1, rows.length) } as CSSProperties;

  return (
    <div className={cn("bf-data-table flex min-h-0 max-w-full flex-col overflow-hidden", className)} style={tableStyle}>
      <div className="bf-scrollbar min-h-0 max-w-full overflow-auto">
        <table className="w-full min-w-[760px] table-fixed border-collapse">
          <thead>
            <tr className="border-b border-[var(--bf-border-soft)] bg-[#fbfcff]">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    "h-[36px] px-2 text-[13px] font-bold text-[#14203e]",
                    shouldNowrap(column.key, column.nowrap) && "whitespace-nowrap",
                    column.align === "center" && "text-center",
                    column.align === "right" && "text-right",
                    (!column.align || column.align === "left") && "text-left",
                  )}
                  style={{ width: column.width }}
                >
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className={`border-b border-[var(--bf-border-soft)] transition hover:bg-[#fbfdff] ${onRowClick ? "cursor-pointer" : ""}`} onClick={() => onRowClick?.(row, rowIndex)}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "h-[44px] px-2 text-[13px] text-[#111a34] align-middle",
                      column.key === "visible_actions" || column.key === "actions" ? "max-w-none overflow-visible" : "max-w-0 overflow-hidden",
                      shouldNowrap(column.key, column.nowrap) && "whitespace-nowrap",
                      column.align === "center" && "text-center",
                      column.align === "right" && "text-right",
                    )}
                  >
                    {column.render(row, rowIndex)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer ? <div className="bf-data-table-footer flex min-h-[56px] items-center justify-between border-t border-[var(--bf-border-soft)] px-5 py-3">{footer}</div> : null}
    </div>
  );
}

type DataTablePaginationProps = {
  total?: unknown;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
};

export function DataTablePagination({ total = 0, page = 1, pageSize = 20, onPageChange }: DataTablePaginationProps) {
  const totalCount = Number(total) || 0;
  const currentPage = Math.max(1, Number(page) || 1);
  const size = Math.max(1, Number(pageSize) || 20);
  const pageCount = Math.max(1, Math.ceil(totalCount / size));
  const prevDisabled = currentPage <= 1;
  const nextDisabled = currentPage >= pageCount;

  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-2 text-xs text-[var(--bf-text-secondary)]">
      <span className="font-semibold">共 {new Intl.NumberFormat("zh-CN").format(totalCount)} 条记录</span>
      <div className="flex items-center gap-3">
        <span>第 {currentPage} / {pageCount} 页</span>
        <span className="rounded-[var(--bf-radius-control)] bg-[#f8fafc] px-3 py-2 font-semibold text-[#1b2848]">每页 {size} 条</span>
        <button
          type="button"
          className="h-8 rounded-[var(--bf-radius-control)] border border-[#dce4f2] bg-white px-2.5 font-semibold text-[#1b2848] disabled:cursor-not-allowed disabled:opacity-45"
          disabled={prevDisabled}
          onClick={() => onPageChange?.(currentPage - 1)}
        >
          上一页
        </button>
        <button
          type="button"
          className="h-8 rounded-[var(--bf-radius-control)] border border-[#dce4f2] bg-white px-2.5 font-semibold text-[#1b2848] disabled:cursor-not-allowed disabled:opacity-45"
          disabled={nextDisabled}
          onClick={() => onPageChange?.(currentPage + 1)}
        >
          下一页
        </button>
      </div>
    </div>
  );
}
