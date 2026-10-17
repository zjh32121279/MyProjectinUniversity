import type { ReactNode } from "react";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";

export type FilterOption = {
  label: string;
  value: string;
};

export function SearchInput({ value, onChange, placeholder = "搜索", className = "" }: { value: string; onChange: (value: string) => void; placeholder?: string; className?: string }) {
  return (
    <label className={`bf-search ${className}`}>
      <AppIcon name="search" size={18} className="bf-search__icon" />
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

export function SegmentedFilter({ label, value, options, onChange }: { label?: string; value: string; options: FilterOption[]; onChange: (value: string) => void }) {
  return (
    <div className="bf-segment-wrap">
      {label ? <span className="bf-filter-label">{label}</span> : null}
      <div className="bf-segment">
        {options.map((option) => (
          <button key={option.value} className={value === option.value ? "is-active" : ""} onClick={() => onChange(option.value)} type="button">
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SelectFilter({ label, value, options, onChange, className = "" }: { label?: string; value: string; options: FilterOption[]; onChange: (value: string) => void; className?: string }) {
  return (
    <label className={`bf-select-filter ${className}`}>
      {label ? <span className="bf-filter-label">{label}</span> : null}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export type DataColumn<T> = {
  key: string;
  header: string;
  width?: string;
  align?: "left" | "center" | "right";
  render: (row: T, index: number) => ReactNode;
};

export function DataTable<T>({ rows, columns, rowKey, selectedKey, onRowClick, empty = "暂无数据" }: { rows: T[]; columns: DataColumn<T>[]; rowKey: (row: T) => string; selectedKey?: string; onRowClick?: (row: T) => void; empty?: ReactNode }) {
  if (!rows.length) {
    return <div className="bf-empty-state">{empty}</div>;
  }

  return (
    <div className="bf-table-scroll">
      <table className="bf-data-table">
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={{ width: column.width }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align ? `is-${column.align}` : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const key = rowKey(row);
            return (
              <tr key={key} className={selectedKey === key ? "is-selected" : ""} onClick={onRowClick ? () => onRowClick(row) : undefined}>
                {columns.map((column) => (
                  <td key={column.key} className={column.align ? `is-${column.align}` : undefined}>
                    {column.render(row, index)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function StatusTag({ status }: { status?: string }) {
  const value = (status || "").toLowerCase();
  const active = ["active", "enabled", "success", "normal", "ok"].includes(value);
  const failed = ["disabled", "failed", "error", "denied"].includes(value);
  const label = active ? "启用" : failed ? (value === "disabled" ? "停用" : "失败") : status || "-";
  return <span className={`bf-tag ${active ? "bf-tag--green" : failed ? "bf-tag--red" : "bf-tag--gray"}`}>{label}</span>;
}

export function ResultTag({ result }: { result?: string }) {
  const value = (result || "").toLowerCase();
  const success = ["success", "ok", "done"].includes(value);
  const failed = ["failed", "error", "denied"].includes(value);
  return <span className={`bf-tag ${success ? "bf-tag--green" : failed ? "bf-tag--red" : "bf-tag--gray"}`}>{success ? "成功" : failed ? "失败" : result || "-"}</span>;
}

export function RoleTag({ isSuperAdmin }: { isSuperAdmin?: boolean }) {
  return <span className={`bf-tag ${isSuperAdmin ? "bf-tag--purple" : "bf-tag--blue"}`}>{isSuperAdmin ? "超级管理员" : "普通管理员"}</span>;
}

export function RuleTypeTag({ type }: { type?: string }) {
  const value = type || "";
  const className = value === "business_rule" ? "bf-tag--blue" : value === "notification_rule" ? "bf-tag--orange" : value === "ai_rule" ? "bf-tag--purple" : value === "ai_tool" ? "bf-tag--cyan" : "bf-tag--gray";
  const labelMap: Record<string, string> = {
    business_rule: "业务规则",
    notification_rule: "通知规则",
    ai_rule: "AI 规则",
    ai_tool: "AI 工具能力",
    system_builtin: "系统内置",
  };
  return <span className={`bf-tag ${className}`}>{labelMap[value] || value || "-"}</span>;
}

export function Toolbar({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="bf-toolbar">
      <div className="bf-toolbar__filters">{children}</div>
      {action ? <div className="bf-toolbar__action">{action}</div> : null}
    </div>
  );
}

export function IconButton({ icon, children, onClick, tone = "primary", disabled = false, type = "button" }: { icon?: AppIconName; children: ReactNode; onClick?: () => void; tone?: "primary" | "secondary" | "danger"; disabled?: boolean; type?: "button" | "submit" }) {
  return (
    <button className={`bf-button bf-button--${tone}`} disabled={disabled} onClick={onClick} type={type}>
      {icon ? <AppIcon name={icon} size={18} /> : null}
      {children}
    </button>
  );
}

export function CenterModal({ open, title, subtitle, onClose, children, footer, width = 620 }: { open: boolean; title: ReactNode; subtitle?: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; width?: number }) {
  if (!open) return null;
  return (
    <div className="bf-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="bf-center-modal" style={{ width }} role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <header className="bf-center-modal__header">
          <div className="min-w-0">
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button className="bf-icon-close" onClick={onClose} type="button" aria-label="关闭">
            <AppIcon name="close" size={20} />
          </button>
        </header>
        <div className="bf-center-modal__body">{children}</div>
        {footer ? <footer className="bf-center-modal__footer">{footer}</footer> : null}
      </section>
    </div>
  );
}

export function ConfirmDialog({ open, title, message, confirmText = "确认", cancelText = "取消", tone = "primary", loading = false, onCancel, onConfirm }: { open: boolean; title: string; message: ReactNode; confirmText?: string; cancelText?: string; tone?: "primary" | "danger"; loading?: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (!open) return null;
  return (
    <div className="bf-modal-backdrop" role="presentation">
      <section className="bf-confirm" role="dialog" aria-modal="true">
        <h2>{title}</h2>
        <div className="bf-confirm__message">{message}</div>
        <div className="bf-confirm__actions">
          <IconButton tone="secondary" onClick={onCancel} disabled={loading}>
            {cancelText}
          </IconButton>
          <IconButton tone={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} disabled={loading}>
            {loading ? "处理中..." : confirmText}
          </IconButton>
        </div>
      </section>
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  const current = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="bf-pagination">
      <span>共 {total.toLocaleString("zh-CN")} 条</span>
      <div className="pr-1">
        <button disabled={current <= 1} onClick={() => onChange(Math.max(0, offset - limit))} type="button" aria-label="上一页">
          <AppIcon name="left" size={16} />
        </button>
        <strong>{current}</strong>
        <button disabled={current >= pages} onClick={() => onChange(offset + limit)} type="button" aria-label="下一页">
          <AppIcon name="right" size={16} />
        </button>
        <span>{limit} 条/页</span>
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="bf-field">
      <span>{label}</span>
      <div>{children}</div>
    </div>
  );
}
