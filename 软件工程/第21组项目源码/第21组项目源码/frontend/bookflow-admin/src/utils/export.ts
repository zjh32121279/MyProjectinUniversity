/**
 * Client-side CSV export utilities.
 * Used by catalog export and any other data-export actions in the admin panel.
 */

type AnyRow = Record<string, unknown>;

const CATALOG_CSV_COLUMNS: [string, (row: AnyRow) => string][] = [
  ["图书编号", (r) => String(r.book_code ?? "")],
  ["书名", (r) => String(r.title ?? "")],
  ["作者", (r) => String(r.author ?? "")],
  ["出版社", (r) => String(r.publisher ?? "")],
  ["ISBN", (r) => String(r.isbn ?? "")],
  ["一级分类", (r) => String(r.category_name ?? "")],
  ["二级分类", (r) => String(r.subcategory_name ?? "")],
  ["流通类型", (r) => String(r.circulation_type ?? "")],
  ["主分区", (r) => {
    const zone = r.primary_zone && typeof r.primary_zone === "object" ? (r.primary_zone as AnyRow) : {};
    return String(zone.zone_name ?? zone.zone_code ?? "");
  }],
  ["实体册数", (r) => String(r.total_copies ?? 0)],
  ["可借册数", (r) => String(r.available_copies ?? 0)],
  ["已借册数", (r) => String(r.borrowed_copies ?? 0)],
  ["保留册数", (r) => String(r.reserved_copies ?? 0)],
  ["出版年份", (r) => String(r.publish_year ?? "")],
  ["语言", (r) => String(r.language ?? "")],
];

function escapeCSV(value: string): string {
  if (value.includes(",") || value.includes('"') || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export function downloadCSV(filename: string, columns: [string, (row: AnyRow) => string][], rows: AnyRow[]): void {
  const header = columns.map(([label]) => escapeCSV(label)).join(",");
  const body = rows.map((row) => columns.map(([, getter]) => escapeCSV(getter(row))).join(",")).join("\n");
  const bom = "﻿"; // BOM for Excel UTF-8 compatibility
  const blob = new Blob([bom + header + "\n" + body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function downloadCatalogCSV(rows: AnyRow[]): void {
  const date = new Date().toISOString().slice(0, 10);
  downloadCSV(`bookflow-catalog-${date}.csv`, CATALOG_CSV_COLUMNS, rows);
}
