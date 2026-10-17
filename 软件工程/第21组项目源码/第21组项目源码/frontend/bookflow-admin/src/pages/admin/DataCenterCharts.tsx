import type { ReactNode } from "react";
import type { EChartsOption } from "echarts";
import ReactECharts from "echarts-for-react";
import type { AnyRecord } from "@/types/api";
import { asArray, formatNumber, formatPercent } from "@/utils/format";
import { formatAIName } from "@/utils/labels";

function toNumber(value: unknown, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function InlineChart({ option, height = 300 }: { option?: EChartsOption; height?: number }) {
  if (!option) {
    return <div className="grid h-full min-h-[220px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无图表数据</div>;
  }
  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}

export function CompactCard({ title, actions, children, bodyClassName = "p-5", className = "" }: { title: string; actions?: ReactNode; children: ReactNode; bodyClassName?: string; className?: string }) {
  return (
    <section className={`bf-card overflow-hidden ${className}`}>
      <div className="flex items-center justify-between gap-4 border-b border-[var(--bf-border-soft)] px-6 py-3">
        <h2 className="text-[20px] font-bold text-[#071334]">{title}</h2>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function DonutCenterChart({
  option, height = 300, centerTitle, centerValue, centerLeft = "33%", centerTop = "53%",
}: { option?: EChartsOption; height?: number; centerTitle: string; centerValue: string; centerLeft?: string; centerTop?: string }) {
  if (!option) {
    return <div className="grid h-full min-h-[220px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无图表数据</div>;
  }
  const compactValue = centerValue.replace(/\s+/g, "").length >= 6;
  const tightValue = centerValue.replace(/\s+/g, "").length >= 9;
  return (
    <div className="relative" style={{ height }}>
      <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />
      <div className="pointer-events-none absolute w-[88px] -translate-x-1/2 -translate-y-1/2 text-center" style={{ left: centerLeft, top: centerTop }}>
        <div className="whitespace-nowrap text-[13px] font-black leading-none text-[#17213c]">{centerTitle}</div>
        <div className={`${tightValue ? "text-[16px]" : compactValue ? "text-[18px]" : "text-[24px]"} mt-2 whitespace-nowrap font-black leading-none text-[#071334]`}>{centerValue}</div>
      </div>
    </div>
  );
}

export function nonEmptyTrendWindow(trend: AnyRecord | undefined, size = 7) {
  const rawLabels = asArray<string>(trend?.labels);
  const rawSeries = asArray<{ name: string; data: number[] }>(trend?.series).map((item) => ({ ...item, data: asArray<number>(item.data).map((value) => toNumber(value)) }));
  if (!rawLabels.length || !rawSeries.length) return { labels: [] as string[], series: [] as Array<{ name: string; data: number[] }> };
  let endIndex = rawLabels.length - 1;
  for (let index = rawLabels.length - 1; index >= 0; index -= 1) {
    const total = rawSeries.reduce((sum, item) => sum + toNumber(item.data[index]), 0);
    if (total > 0) { endIndex = index; break; }
  }
  const startIndex = Math.max(0, endIndex - size + 1);
  return { labels: rawLabels.slice(startIndex, endIndex + 1), series: rawSeries.map((item) => ({ ...item, data: item.data.slice(startIndex, endIndex + 1) })) };
}

// --- Chart option builders ---

export function overviewTrendOption(labels: string[], series: Array<{ name: string; data: number[] }>): EChartsOption | undefined {
  if (!labels.length || !series.length) return undefined;
  return {
    animation: false, color: ["#2563eb", "#16a34a"], tooltip: { trigger: "axis" },
    legend: { top: 8, left: 48, itemWidth: 26, itemHeight: 10, textStyle: { color: "#1f2b48", fontSize: 15, fontWeight: 700 } },
    grid: { left: 50, right: 32, top: 80, bottom: 42 },
    xAxis: { type: "category", boundaryGap: true, data: labels.map((item) => item.slice(5)), axisTick: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, axisLabel: { color: "#32405f", fontSize: 14, margin: 16 } },
    yAxis: { type: "value", min: 0, splitNumber: 5, axisLabel: { color: "#32405f", fontSize: 13 }, splitLine: { lineStyle: { color: "#e9eff8" } } },
    series: series.map((item) => ({
      name: item.name === "borrow" ? "借出" : item.name === "return" ? "归还" : item.name, type: "line", smooth: false, symbol: "circle", symbolSize: 10, lineStyle: { width: 3 },
      label: { show: true, position: "top", color: item.name === "return" ? "#16a34a" : "#2563eb", fontSize: 14, fontWeight: 800, formatter: (params: any) => (toNumber(params.value) > 0 ? String(params.value) : "") },
      emphasis: { focus: "series" }, data: item.data,
    })),
  };
}

export const overviewTaskPieColors = ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#4f46e5", "#94a3b8"];

export function overviewTaskPieOption(items: Array<{ name: string; value: number }>): EChartsOption | undefined {
  if (!items.length) return undefined;
  return {
    animation: false,
    color: overviewTaskPieColors,
    tooltip: { trigger: "item", formatter: "{b}<br/>{c} 条（{d}%）" },
    series: [{
      type: "pie",
      radius: ["50%", "72%"],
      center: ["50%", "52%"],
      avoidLabelOverlap: true,
      minAngle: 0,
      stillShowZeroSum: true,
      label: { show: false },
      labelLine: { show: false },
      data: items,
    }],
  };
}

export function simpleDonutOption(items: Array<{ name: string; value: number }>, center: [string, string] = ["50%", "52%"]): EChartsOption | undefined {
  if (!items.length) return undefined;
  return { animation: false, color: ["#2563eb", "#16a34a", "#f59e0b", "#ef4444"], tooltip: { trigger: "item", formatter: "{b}<br/>{c} 册（{d}%）" }, series: [{ type: "pie", radius: ["60%", "76%"], center, avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false }, data: items }] };
}

export function hotColdBubbleOption(items: Array<{ name: string; borrow: number; copies: number; size: number; hot: number; cold: number }>): EChartsOption | undefined {
  if (!items.length) return undefined;
  const maxCopies = Math.max(...items.map((item) => item.copies), 1);
  const maxBorrow = Math.max(...items.map((item) => item.borrow), 1);
  const xMid = Math.round(maxCopies * 0.52);
  const yMid = Math.round(maxBorrow * 0.52);
  return {
    animation: false, color: ["#f87171", "#fb923c", "#fdba74", "#60a5fa", "#818cf8", "#34d399", "#86efac", "#f59e0b"],
    tooltip: { formatter: (params: any) => { const value = params.value as number[]; return `${params.name}<br/>馆藏量：${formatNumber(value[0])}<br/>近 90 天借阅：${formatNumber(value[1])}<br/>热门/冷门：${formatNumber(value[3])}/${formatNumber(value[4])}`; } },
    grid: { left: 58, right: 30, top: 42, bottom: 58 },
    xAxis: { name: "馆藏量", min: 0, max: Math.ceil(maxCopies * 1.08), splitNumber: 4, nameTextStyle: { color: "#95a0b8", fontWeight: 700 }, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, splitLine: { lineStyle: { color: "#edf2f8" } } },
    yAxis: { name: "借阅量", min: 0, max: Math.ceil(maxBorrow * 1.1), splitNumber: 4, nameTextStyle: { color: "#95a0b8", fontWeight: 700 }, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, splitLine: { lineStyle: { color: "#edf2f8" } } },
    graphic: [
      { type: "text", right: 22, top: 36, style: { text: "热门 · 馆藏多", fill: "#f97316", fontSize: 13, fontWeight: 800 } },
      { type: "text", left: 74, top: 36, style: { text: "热门 · 馆藏少", fill: "#ef4444", fontSize: 13, fontWeight: 800 } },
      { type: "text", right: 22, bottom: 38, style: { text: "冷门 · 馆藏多", fill: "#2563eb", fontSize: 13, fontWeight: 800 } },
      { type: "text", left: 74, bottom: 38, style: { text: "冷门 · 馆藏少", fill: "#16a34a", fontSize: 13, fontWeight: 800 } },
      { type: "text", left: "center", bottom: 8, style: { text: "气泡大小表示热门/冷门图书数量", fill: "#64708b", fontSize: 12, fontWeight: 700 } },
    ],
    series: [{ type: "scatter", symbolSize: (value: number[]) => Math.max(34, Math.min(78, value[2])),
      markLine: { silent: true, symbol: ["none", "none"], lineStyle: { type: "dashed", color: "#c8d4e6", width: 1 }, data: [{ xAxis: xMid }, { yAxis: yMid }], label: { show: false } },
      data: items.map((item) => ({ name: item.name, value: [item.copies, item.borrow, item.size, item.hot, item.cold] })),
      label: { show: true, formatter: "{b}", color: "#111a34", fontSize: 12, fontWeight: 800 }, labelLayout: { hideOverlap: true }, itemStyle: { opacity: 0.68 } }],
  };
}

export function readerTrendOption(labels: string[], newTrend: number[], activeTrend: number[]): EChartsOption | undefined {
  if (!labels.length) return undefined;
  return {
    animation: false, color: ["#2563eb", "#16a34a"], tooltip: { trigger: "axis" },
    legend: { top: 8, left: "center", itemWidth: 24, itemHeight: 10, textStyle: { color: "#1f2b48", fontSize: 13, fontWeight: 700 } },
    grid: { left: 54, right: 36, top: 62, bottom: 34 },
    xAxis: { type: "category", data: labels, axisTick: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, axisLabel: { color: "#32405f", fontSize: 12 } },
    yAxis: { type: "value", min: 0, splitNumber: 4, axisLabel: { color: "#64708b", fontSize: 11 }, splitLine: { lineStyle: { color: "#edf2f8" } } },
    series: [
      { name: "新增读者", type: "line", smooth: true, symbol: "circle", symbolSize: 8, lineStyle: { width: 3 }, label: { show: true, position: "top", color: "#2563eb", fontSize: 11, fontWeight: 800 }, data: newTrend },
      { name: "活跃读者", type: "line", smooth: true, symbol: "circle", symbolSize: 8, lineStyle: { width: 3 }, label: { show: true, position: "top", color: "#16a34a", fontSize: 11, fontWeight: 800 }, data: activeTrend },
    ],
  };
}

export function creditScoreOption(items: Array<{ name: string; count: number }>): EChartsOption | undefined {
  if (!items.length) return undefined;
  return {
    animation: false, color: ["#2563eb"], tooltip: { trigger: "axis" }, grid: { left: 46, right: 18, top: 24, bottom: 32 },
    xAxis: { type: "category", data: items.map((item) => item.name), axisTick: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, axisLabel: { interval: 0, color: "#32405f", fontSize: 11, fontWeight: 700 } },
    yAxis: { type: "value", min: 0, splitNumber: 3, axisLabel: { color: "#64708b", fontSize: 11 }, splitLine: { lineStyle: { color: "#edf2f8" } } },
    series: [{ type: "bar", barWidth: 28, data: items.map((item) => item.count), itemStyle: { borderRadius: [7, 7, 0, 0] }, label: { show: true, position: "top", color: "#17213c", fontSize: 11, fontWeight: 800, formatter: (params: any) => (toNumber(params.value) > 0 ? formatNumber(params.value) : "") } }],
  };
}

export function aiTrendOption(trend: AnyRecord | undefined): EChartsOption | undefined {
  const labels = asArray<string>(trend?.labels);
  const series = asArray<{ name: string; data: number[] }>(trend?.series).map((item) => ({ name: aiDisplayName(item.name), data: asArray<number>(item.data).map((value) => toNumber(value)) })).filter((item) => item.data.some((value) => value > 0));
  if (!labels.length || !series.length) return undefined;
  return {
    animation: false, color: ["#2563eb", "#ef4444", "#16a34a"], tooltip: { trigger: "axis", valueFormatter: (value) => `${value}%` },
    legend: { top: 8, left: 72, itemWidth: 26, itemHeight: 10, textStyle: { color: "#1f2b48", fontSize: 13, fontWeight: 700 } },
    grid: { left: 54, right: 34, top: 62, bottom: 38 },
    xAxis: { type: "category", data: labels.map((item) => item.slice(5) || item), axisTick: { show: false }, axisLine: { lineStyle: { color: "#d9e2f1" } }, axisLabel: { color: "#32405f", fontSize: 12, fontWeight: 700 } },
    yAxis: { type: "value", min: 0, max: 100, splitNumber: 4, axisLabel: { formatter: "{value}%", color: "#32405f", fontSize: 12 }, splitLine: { lineStyle: { color: "#e9eff8" } } },
    series: series.map((item) => ({ name: item.name, type: "line", smooth: true, symbol: "circle", symbolSize: 8, lineStyle: { width: 3 },
      label: { show: true, position: "top", color: item.name.includes("转") ? "#ef4444" : "#2563eb", fontSize: 11, fontWeight: 800, formatter: (params: any) => `${toNumber(params.value).toFixed(1)}%` }, data: item.data })),
  };
}

export function aiPieOption(items: Array<{ name: string; value: number }>, center: [string, string] = ["32%", "52%"]): EChartsOption | undefined {
  if (!items.length || !items.some((item) => item.value > 0)) return undefined;
  return { animation: false, color: ["#2563eb", "#22c55e", "#f59e0b", "#8b5cf6", "#06b6d4", "#f43f5e", "#64748b"], tooltip: { trigger: "item", formatter: "{b}<br/>{c} 次（{d}%）" }, series: [{ type: "pie", radius: ["42%", "66%"], center, label: { show: true, formatter: "{d}%", color: "#fff", fontSize: 12, fontWeight: 800 }, labelLine: { show: false }, data: items }] };
}

export function aiHorizontalBarOption(items: Array<{ name: string; count: number }>): EChartsOption | undefined {
  const rows = items.filter((item) => item.count > 0).slice(0, 5);
  if (!rows.length) return undefined;
  return {
    animation: false, color: ["#2563eb"], tooltip: { trigger: "axis" }, grid: { left: 104, right: 56, top: 18, bottom: 24 },
    xAxis: { type: "value", axisLine: { lineStyle: { color: "#d9e2f1" } }, axisLabel: { color: "#32405f", fontSize: 12 }, splitLine: { lineStyle: { color: "#edf2f8" } } },
    yAxis: { type: "category", inverse: true, data: rows.map((item) => item.name), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: "#17213c", fontSize: 12, fontWeight: 700, width: 90, overflow: "truncate" } },
    series: [{ type: "bar", barWidth: 15, itemStyle: { borderRadius: [0, 7, 7, 0] }, label: { show: true, position: "right", color: "#17213c", fontSize: 12, fontWeight: 800, formatter: (params: any) => `${formatNumber(params.value)} 次` }, data: rows.map((item) => item.count) }],
  };
}

export function aiDisplayName(name: unknown) {
  return formatAIName(name);
}

export function centerPieOption(items: Array<{ name: string; value: number }>, centerTitle: string, centerValue: string): EChartsOption | undefined {
  if (!items.length) return undefined;
  return {
    color: ["#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"],
    tooltip: { trigger: "item" },
    legend: { orient: "vertical", right: 18, top: "middle", itemGap: 14, textStyle: { color: "#1f2b48", fontSize: 13 } },
    graphic: [
      { type: "text", left: "29%", top: "43%", style: { text: centerTitle, fill: "#66708a", fontSize: 13, fontWeight: 700, align: "center" } },
      { type: "text", left: "28.5%", top: "50%", style: { text: centerValue, fill: "#071334", fontSize: 24, fontWeight: 900, align: "center" } },
    ],
    series: [{ type: "pie", radius: ["42%", "68%"], center: ["34%", "52%"], avoidLabelOverlap: true, label: { formatter: "{d}%", color: "#fff", fontWeight: 800 }, labelLine: { show: false }, data: items }],
  };
}

export function heatmapOption(rows: Array<{ zone: string; label: string; inRack: number; useRate: number; staleRate: number }>): EChartsOption | undefined {
  if (!rows.length) return undefined;
  const metrics = ["在架率", "利用率", "滞销率"];
  const data = rows.flatMap((row, x) => [[x, 0, row.inRack], [x, 1, row.useRate], [x, 2, row.staleRate]]);
  return {
    tooltip: { position: "top", formatter: (params: any) => `${rows[Number((params.value as number[])[0])]?.label}<br/>${metrics[Number((params.value as number[])[1])]}：${(params.value as number[])[2]}%` },
    grid: { left: 88, right: 28, top: 58, bottom: 36 },
    xAxis: { type: "category", data: rows.map((row) => `${row.zone}\n${row.label}`), splitArea: { show: true }, axisLabel: { color: "#111a34", fontWeight: 700, lineHeight: 18 } },
    yAxis: { type: "category", data: metrics, splitArea: { show: true }, axisLabel: { color: "#111a34", fontWeight: 700 } },
    visualMap: { min: 0, max: 100, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#f87171", "#fbbf24", "#a7e163", "#22c55e"] }, text: ["优秀", "较差"], calculable: false },
    series: [{ type: "heatmap", data, label: { show: true, formatter: (params: any) => `${(params.value as number[])[2]}%`, fontWeight: 800 }, emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.18)" } } }],
  };
}

export function funnelOption(items: Array<{ name: string; value: number }>): EChartsOption | undefined {
  if (!items.length) return undefined;
  return {
    color: ["#2563eb", "#22c55e", "#f59e0b", "#8b5cf6", "#06b6d4"],
    tooltip: { trigger: "item" },
    series: [{ type: "funnel", left: "8%", top: 20, width: "82%", height: "84%", sort: "descending", gap: 2, label: { position: "right", color: "#111a34", fontWeight: 700 }, itemStyle: { borderColor: "#fff", borderWidth: 2 }, data: items }],
  };
}

export { toNumber };
