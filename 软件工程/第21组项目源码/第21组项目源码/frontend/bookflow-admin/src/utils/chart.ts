import type { EChartsOption } from "echarts";
import { asArray } from "@/utils/format";

const chartColors = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#0891b2", "#ef4444", "#64748b"];

const grid = { left: 42, right: 20, top: 46, bottom: 34 };

const chartNameLabels: Record<string, string> = {
  borrow: "借出",
  return: "归还",
  pending: "待处理",
  claimed: "处理中",
  resolved: "已完成",
  cancelled: "已取消",
  hot: "热门",
  normal: "普通",
  cold: "冷门",
  S01: "在馆可借",
  S02: "已借出",
  S03: "预约保留",
  S04: "暂不可借",
};

function chartLabel(value: unknown) {
  const key = String(value ?? "-");
  return chartNameLabels[key] ?? key;
}

export function lineOption(labels: unknown, series: unknown): EChartsOption | undefined {
  const labelList = asArray<string>(labels);
  const seriesList = asArray<{ name: string; data: number[] }>(series);
  if (!labelList.length || !seriesList.length) return undefined;
  return {
    color: chartColors,
    tooltip: { trigger: "axis" },
    legend: { top: 8, textStyle: { color: "#26324d" } },
    grid,
    xAxis: { type: "category", data: labelList.map((item) => item.slice(5)), axisLine: { lineStyle: { color: "#d9e2f1" } } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#edf2f8" } } },
    series: seriesList.map((item) => ({
      name: chartLabel(item.name),
      type: "line",
      smooth: true,
      symbolSize: 8,
      data: item.data,
    })),
  };
}

export function barOption(items: unknown, nameKey = "name", valueKey = "count"): EChartsOption | undefined {
  const rows = asArray<Record<string, unknown>>(items);
  if (!rows.length) return undefined;
  return {
    color: ["#2563eb"],
    tooltip: { trigger: "axis" },
    grid,
    xAxis: { type: "category", data: rows.map((item) => String(item[nameKey] ?? "-")), axisLabel: { interval: 0, rotate: rows.length > 6 ? 24 : 0 } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#edf2f8" } } },
    series: [{ type: "bar", barWidth: 22, data: rows.map((item) => Number(item[valueKey] ?? 0)), itemStyle: { borderRadius: [6, 6, 0, 0] } }],
  };
}

export function pieOption(items: unknown, centerLabel?: string): EChartsOption | undefined {
  const rows = asArray<Record<string, unknown>>(items);
  if (!rows.length) return undefined;
  const pieData = rows.map((item) => ({ name: chartLabel(item.name ?? item.status ?? "-"), value: Number(item.count ?? item.value ?? 0) }));
  return {
    color: chartColors,
    tooltip: { trigger: "item" },
    legend: { orient: "vertical", right: 18, top: "middle", itemGap: 14, textStyle: { color: "#26324d", fontSize: 13 } },
    series: [
      {
        name: centerLabel,
        type: "pie",
        radius: ["38%", "64%"],
        center: ["35%", "52%"],
        data: pieData,
        label: { show: false },
        labelLine: { show: false },
      },
    ],
  };
}

export function horizontalBarOption(items: unknown, nameKey = "name", valueKey = "count"): EChartsOption | undefined {
  const rows = asArray<Record<string, unknown>>(items).slice(0, 8).reverse();
  if (!rows.length) return undefined;
  return {
    color: ["#2563eb"],
    tooltip: { trigger: "axis" },
    grid: { left: 120, right: 28, top: 28, bottom: 24 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#edf2f8" } } },
    yAxis: { type: "category", data: rows.map((item) => String(item[nameKey] ?? "-")) },
    series: [{ type: "bar", data: rows.map((item) => Number(item[valueKey] ?? 0)), itemStyle: { borderRadius: [0, 7, 7, 0] } }],
  };
}
