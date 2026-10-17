import { useState, useRef, useEffect } from "react";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { BookCover } from "@/components/ui/BookCover";
import { StatCard } from "@/components/ui/StatCard";
import type { AnyRecord } from "@/types/api";
import { barOption } from "@/utils/chart";
import { asArray, formatNumber, formatPercent } from "@/utils/format";
import {
  CompactCard, DonutCenterChart, InlineChart, aiDisplayName, aiHorizontalBarOption,
  aiPieOption, aiTrendOption, creditScoreOption,
  hotColdBubbleOption, overviewTaskPieColors, overviewTaskPieOption, overviewTrendOption,
  readerTrendOption, simpleDonutOption, toNumber,
} from "./DataCenterCharts";

const RANGE_OPTIONS = [
  { days: 7, label: "近七天" },
  { days: 14, label: "近十四天" },
  { days: 30, label: "近三十天" },
];

const categoryLabels: Record<string, string> = { C01: "少儿绘本", C02: "儿童文学", C03: "青少年科普", C04: "教辅考试", C05: "文学小说", C06: "诗歌散文", C07: "历史传记", C08: "社会科学", C09: "法律公共知识", C10: "经济管理", C11: "生活健康", C12: "艺术休闲", C13: "计算机技术", C14: "自然科学", C15: "语言学习", C16: "地方文献", C17: "工具书", C18: "期刊资料" };
const categoryIdLabels: Record<string, string> = { "1": "少儿绘本", "2": "儿童文学", "3": "青少年科普", "4": "教辅考试", "5": "文学小说", "6": "诗歌散文", "7": "历史传记", "8": "社会科学", "9": "法律公共知识", "10": "经济管理", "11": "生活健康", "12": "艺术休闲", "13": "计算机技术", "14": "自然科学", "15": "语言学习", "16": "地方文献", "17": "工具书", "18": "期刊资料" };
const readerTypeLabels: Record<string, string> = { adult: "成人读者", child: "儿童读者", teen: "青少年读者", senior: "老年读者", institution: "机构账号" };
const activityLevelLabels = ["高频活跃 10次以上", "中频活跃 3-9次", "低频活跃 1-2次", "沉睡 0次"];
const taskStatusKeys = ["pending", "ai_processing", "waiting_human", "admin_processing", "resolved", "cancelled"] as const;
const copyStatusKeys = ["available", "borrowed", "reserved", "unavailable"] as const;
const statusColorClasses = ["bg-blue-500", "bg-green-500", "bg-amber-500", "bg-red-500"];

function percent(value: number, total: number) { return total ? `${((value / total) * 100).toFixed(1)}%` : "0.0%"; }
function ratioValue(value: unknown, fallback = 0) { const n = Number(value); if (!Number.isFinite(n)) return fallback; return n > 1 ? n / 100 : n; }
function formatDuration(secondsValue: unknown) {
  const rawSeconds = Math.max(0, Number(secondsValue) || 0);
  if (rawSeconds > 0 && rawSeconds < 1) return "不足1秒";
  const totalSeconds = Math.round(rawSeconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}时${minutes ? `${minutes}分` : ""}${seconds ? `${seconds}秒` : ""}`;
  if (minutes > 0) return `${minutes}分${seconds ? `${seconds}秒` : ""}`;
  return `${seconds}秒`;
}
function creditBucketLabel(key: unknown) { const value = String(key ?? ""); const labels: Record<string, string> = { very_high: "90-100", high: "80-89", good: "70-79", mid: "60-69", low: "60 以下" }; return labels[value] ?? (value || "未分组"); }
function creditBucketOrder(name: string) { const order: Record<string, number> = { "90-100": 1, "80-89": 2, "70-79": 3, "60-69": 4, "60 以下": 5 }; return order[name] ?? 99; }
function statusLabel(key: string) { const labels: Record<string, string> = { available: "在馆可借", borrowed: "已借出", reserved: "预约保留", unavailable: "暂不可借" }; return labels[key] ?? key; }
function categoryLabel(key: unknown) { const code = String(key ?? ""); return categoryLabels[code] ?? categoryIdLabels[code] ?? (code || "未分类"); }
function readerTypeLabel(key: unknown) { const code = String(key ?? ""); return readerTypeLabels[code] ?? (code || "未知类型"); }
function activityLevelLabel(key: unknown, index: number) {
  const value = String(key ?? "").trim();
  const labels: Record<string, string> = { high: activityLevelLabels[0], medium: activityLevelLabels[1], mid: activityLevelLabels[1], low: activityLevelLabels[2], sleep: activityLevelLabels[3], sleeping: activityLevelLabels[3], dormant: activityLevelLabels[3] };
  return labels[value] ?? activityLevelLabels[index] ?? (value || "未分层");
}
function taskStatusLabel(key: unknown) { const value = String(key ?? ""); const labels: Record<string, string> = { pending: "待处理", ai_processing: "AI处理中", waiting_human: "待人工介入", admin_processing: "人工处理中", resolved: "已完成", cancelled: "已取消" }; return labels[value] ?? (value || "未知状态"); }

function RangeButton({ days, onChange }: { days: number; onChange: (days: number) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const label = RANGE_OPTIONS.find((o) => o.days === days)?.label ?? "近七天";

  useEffect(() => {
    function handleClick(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="inline-flex h-10 items-center gap-2 rounded-xl border border-[#d9e4f5] bg-gradient-to-b from-white to-[#f7faff] px-4 text-sm font-black text-[#17213c] shadow-[0_6px_14px_rgba(31,68,135,0.045)] transition hover:border-[#b8c9e8] hover:bg-[#f8fbff]"
        onClick={() => setOpen(!open)}
      >
        <span>{label}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-30 mt-1 w-36 rounded-xl border border-[#e7edf7] bg-white py-1 shadow-[0_16px_40px_rgba(15,23,42,0.12)]">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
              className={`block w-full px-4 py-2.5 text-left text-[13px] font-bold transition ${opt.days === days ? "bg-[#f4f0ff] text-[#4f46e5]" : "text-[#17213c] hover:bg-[#f8fbff]"}`}
              onClick={() => { onChange(opt.days); setOpen(false); }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ReaderActivityLevelChart({ rows }: { rows: Array<{ name: string; value: number }> }) {
  const visibleRows = rows.filter((row) => row.value >= 0);
  if (!visibleRows.length) {
    return <div className="grid h-[210px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无活跃度数据</div>;
  }
  const maxValue = Math.max(...visibleRows.map((row) => row.value), 1);
  const total = visibleRows.reduce((sum, row) => sum + row.value, 0);
  const colors = ["#f59e0b", "#8b5cf6", "#22c55e", "#2563eb"];
  return (
    <div className="flex h-[184px] min-w-0 flex-col justify-center gap-2">
      {visibleRows.map((row, index) => {
        const width = `${Math.max(8, (row.value / maxValue) * 100)}%`;
        return (
          <div key={row.name} className="grid min-w-0 grid-cols-[minmax(96px,140px)_minmax(0,1fr)_86px] items-center gap-3 text-[11.5px] font-black text-[#17213c]">
            <span className="truncate" title={row.name}>{row.name}</span>
            <span className="block h-3 rounded-full bg-[#edf2f8]">
              <i className="block h-3 rounded-full" style={{ width, background: colors[index % colors.length] }} />
            </span>
            <span className="whitespace-nowrap text-right leading-tight">
              {formatNumber(row.value)} 人
              <span className="block text-[10.5px] font-bold text-[#64708b]">{percent(row.value, total)}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function healthCellClass(value: number, metric: "inRack" | "useRate" | "staleRate") {
  if (metric === "inRack") { if (value >= 90) return "bg-[#80d465] text-[#071334]"; if (value >= 75) return "bg-[#b6e86f] text-[#071334]"; if (value >= 50) return "bg-[#ffe066] text-[#071334]"; if (value >= 25) return "bg-[#ffad4d] text-[#071334]"; return "bg-[#ff6b6b] text-white"; }
  if (metric === "useRate") { if (value >= 50) return "bg-[#80d465] text-[#071334]"; if (value >= 25) return "bg-[#ffe066] text-[#071334]"; return "bg-[#ff8a65] text-white"; }
  if (value <= 10) return "bg-[#9bdd70] text-[#071334]"; if (value <= 20) return "bg-[#ffe066] text-[#071334]"; if (value <= 30) return "bg-[#ffad4d] text-[#071334]"; return "bg-[#ff6b6b] text-white";
}

function OverviewStatCard({ title, value, unit, icon, tone }: { title: string; value: string | number; unit?: string; icon: string; tone: "blue" | "green" | "orange" | "red" | "purple" }) {
  return (
    <div className="bf-card flex h-[160px] min-w-0 items-center gap-6 rounded-[14px] px-8 py-6 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
      <FeatureIcon name={icon} tone={tone} size="xl" />
      <div className="min-w-0"><div className="whitespace-nowrap text-[16px] font-black text-[#17213c]">{title}</div><div className="mt-3 flex items-baseline gap-3"><span className="whitespace-nowrap text-[42px] font-black leading-none text-[#071334]">{value}</span>{unit ? <span className="whitespace-nowrap text-[18px] font-black text-[#17213c]">{unit}</span> : null}</div></div>
    </div>
  );
}

function HotColdSummaryCard({ title, value, unit, icon, tone, sub }: { title: string; value: string | number; unit: string; icon: string; tone: "blue" | "green" | "orange" | "red" | "purple" | "cyan" | "gray"; sub: string }) {
  return (
    <div className="bf-card flex h-[84px] items-center gap-4 rounded-2xl px-5 py-3">
      <FeatureIcon name={icon} tone={tone} size="md" /><div className="min-w-0 flex-1"><div className="text-[15px] font-black text-[#17213c]">{title}</div><div className="mt-1 flex items-baseline gap-1.5"><span className="text-[24px] font-black leading-none text-[#071334]">{value}</span><span className="text-sm font-black text-[#17213c]">{unit}</span></div><div className="mt-1 truncate text-xs font-bold text-[#64708b]">{sub}</div></div>
    </div>
  );
}

function BookRankingPanel({ title, tone, rows, valueKey, extraKey, empty, rangeDays, onRangeChange }: { title: string; tone: "hot" | "cold"; rows: AnyRecord[]; valueKey: string; extraKey: string; empty: string; rangeDays: number; onRangeChange: (days: number) => void }) {
  const colors = tone === "hot" ? ["#ef4444", "#f97316", "#f59e0b"] : ["#2563eb", "#64748b", "#94a3b8"];
  const valueHeader = "借阅次数";
  const extraHeader = tone === "hot" ? "预约次数" : "距上次借阅";
  return (
    <CompactCard title={title} actions={<RangeButton days={rangeDays} onChange={onRangeChange} />} bodyClassName="px-4 pb-2.5 pt-2" className="h-[468px]">
      {rows.length ? (<div className="space-y-1.5">
        <div className="grid grid-cols-[30px_minmax(0,1fr)_54px_82px] items-center gap-2 px-1 pb-0.5 text-[11px] font-black text-[#66708a]"><span className="whitespace-nowrap">排名</span><span className="whitespace-nowrap">书名</span><span className="whitespace-nowrap text-right">{valueHeader}</span><span className="whitespace-nowrap text-right">{extraHeader}</span></div>
        {rows.map((row, index) => (
          <div key={String(row.book_code ?? index)} className="grid h-[61px] grid-cols-[30px_34px_minmax(0,1fr)_52px_82px] items-center gap-2 rounded-2xl border border-[#e5ecf7] bg-[#fbfcff] px-3 shadow-[0_8px_16px_rgba(15,23,42,0.025)]">
            <div className="grid h-7 w-7 place-items-center rounded-lg text-sm font-black text-white" style={{ background: colors[Math.min(index, 2)] ?? "#d9e2f1", color: index > 2 ? "#24304f" : "#fff" }}>{index + 1}</div>
            <BookCover title={String(row.title ?? "")} code={String(row.book_code ?? "")} coverUrl={String(row.cover_url ?? "")} size="sm" className="h-[46px] w-[34px] rounded-md" />
            <div className="min-w-0"><div className="truncate text-[14px] font-black text-[#101a35]">{String(row.title ?? "-")}</div><div className="mt-0.5 truncate text-[11px] font-semibold text-[#44506b]">{String(row.author ?? row.book_code ?? "-")}</div></div>
            <div className="whitespace-nowrap text-right text-[14px] font-black text-[var(--bf-brand)]">{formatNumber(row[valueKey])}</div>
            <div className="whitespace-nowrap text-right text-[13px] font-black text-[var(--bf-brand)]">{tone === "hot" ? `${formatNumber(row[extraKey])} 次` : `${formatNumber(row[extraKey])} 天`}</div>
          </div>))}
      </div>) : (<div className="py-24 text-center font-semibold text-[var(--bf-text-secondary)]">{empty}</div>)}
    </CompactCard>
  );
}

function HealthGrid({ rows }: { rows: Array<{ zone: string; label: string; inRack: number; useRate: number; staleRate: number }> }) {
  const metrics = [
    { key: "inRack", label: "在架率" },
    { key: "useRate", label: "利用率" },
    { key: "staleRate", label: "滞销率" },
  ] as const;
  if (!rows.length) return <div className="grid min-h-[260px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无热力图数据</div>;
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-[#e7edf7] bg-white">
      <div className="grid min-w-0" style={{ gridTemplateColumns: `96px repeat(${rows.length}, minmax(0, 1fr))` }}>
        <div className="border-b border-r border-[#e7edf7] bg-[#f8fbff] px-3 py-3 text-xs font-black text-[#66708a]">指标</div>
        {rows.map((row) => (
          <div key={row.zone} className="min-w-0 border-b border-r border-[#e7edf7] bg-[#f8fbff] px-2 py-2 text-center last:border-r-0">
            <div className="truncate text-xs font-black text-[#17213c]">{row.label}</div>
            <div className="mt-0.5 truncate text-[10px] font-bold text-[#7b879c]">{row.zone}</div>
          </div>
        ))}
        {metrics.map((metric) => (
          <div key={metric.key} className="contents">
            <div className="flex items-center border-r border-t border-[#e7edf7] bg-[#fbfcff] px-3 text-sm font-black text-[#17213c]">{metric.label}</div>
            {rows.map((row) => {
              const value = row[metric.key];
              return (
                <div key={`${row.zone}-${metric.key}`} className={`grid h-[70px] min-w-0 place-items-center border-r border-t border-white/25 px-1 text-sm font-black ${healthCellClass(value, metric.key)}`}>
                  {`${Number(value).toFixed(value % 1 ? 1 : 0)}%`}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Tab components ---

export function OverviewTab({ data }: { data: AnyRecord; loading: boolean }) {
  const [borrowTrendDays, setBorrowTrendDays] = useState(7);
  const [taskDays, setTaskDays] = useState(7);
  const trend = data.last_30_days_borrow_return_trend as AnyRecord | undefined;
  // 直接取最近 N 天，不对尾部零值做裁剪，与超管端行为保持一致
  const trendRawLabels = asArray<string>(trend?.labels);
  const trendRawSeries = asArray<{ name: string; data: number[] }>(trend?.series).map((item) => ({ ...item, data: asArray<number>(item.data).map((value) => toNumber(value)) }));
  const trendSliceStart = Math.max(0, trendRawLabels.length - borrowTrendDays);
  const trendLabels = trendRawLabels.slice(trendSliceStart);
  const trendSeries = trendRawSeries.map((item) => ({ ...item, data: item.data.slice(trendSliceStart) }));
  const rawTaskItems = asArray<AnyRecord>((data.task_status_distribution as AnyRecord | undefined)?.items);
  const taskValueMap = new Map(rawTaskItems.map((item) => [String(item.name ?? item.status ?? ""), toNumber(item.count ?? item.value)]));
  const taskDistribution = [...taskStatusKeys.map((key) => ({ name: taskStatusLabel(key), value: taskValueMap.get(key) ?? 0 })), ...rawTaskItems.filter((item) => !taskStatusKeys.includes(String(item.name ?? item.status ?? "") as typeof taskStatusKeys[number])).map((item) => ({ name: taskStatusLabel(item.name ?? item.status), value: toNumber(item.count ?? item.value) })).filter((item) => item.value > 0)];
  const statCards = [
    { title: "今日借出", value: formatNumber(data.today_borrow_count), unit: "册", icon: "borrow", tone: "blue" as const },
    { title: "今日归还", value: formatNumber(data.today_return_count), unit: "册", icon: "return", tone: "green" as const },
    { title: "今日到期", value: formatNumber(data.due_today_count), unit: "册", icon: "reservation", tone: "orange" as const },
    { title: "当前逾期", value: formatNumber(data.overdue_count), unit: "册", icon: "risk", tone: "red" as const },
  ];
  const taskLabel = RANGE_OPTIONS.find((o) => o.days === taskDays)?.label ?? "近七天";

  return (
    <div className="space-y-[20px]">
      <div className="grid grid-cols-1 gap-[18px] sm:grid-cols-2 2xl:grid-cols-4">{statCards.map((card) => <OverviewStatCard key={card.title} {...card} />)}</div>
      <div className="grid grid-cols-1 gap-[20px] xl:grid-cols-2">
        <CompactCard title="借还趋势" actions={<RangeButton days={borrowTrendDays} onChange={setBorrowTrendDays} />} bodyClassName="px-6 pb-6 pt-4" className="h-[501px]">
          <InlineChart option={overviewTrendOption(trendLabels, trendSeries)} height={385} />
        </CompactCard>
        <CompactCard title="任务状态分布" actions={<RangeButton days={taskDays} onChange={setTaskDays} />} bodyClassName="px-6 pb-6 pt-4" className="h-[501px]">
          <div className="grid h-[399px] grid-cols-[minmax(0,300px)_minmax(250px,1fr)] items-center gap-8">
            <DonutCenterChart option={overviewTaskPieOption(taskDistribution)} height={330} centerTitle={taskLabel} centerValue={`${formatNumber(taskDistribution.reduce((sum, item) => sum + item.value, 0))} 条`} centerLeft="50%" centerTop="52%" />
            <div className="min-w-0 space-y-3">
              {taskDistribution.map((item, index) => {
                const taskTotal = taskDistribution.reduce((sum, row) => sum + row.value, 0);
                return (
                  <div key={item.name} className="grid grid-cols-[minmax(0,1fr)_78px_70px] items-center gap-3 text-[14px] font-black text-[#17213c]">
                    <span className="flex min-w-0 items-center gap-2 truncate">
                      <i className="h-3.5 w-3.5 shrink-0 rounded-[4px]" style={{ background: overviewTaskPieColors[index % overviewTaskPieColors.length] }} />
                      {item.name}
                    </span>
                    <span className="whitespace-nowrap text-right">{formatNumber(item.value)} 条</span>
                    <span className="whitespace-nowrap text-right text-[#64708b]">{percent(item.value, taskTotal)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </CompactCard>
      </div>
    </div>
  );
}

export function CollectionTab({ data }: { data: AnyRecord; loading: boolean }) {
  const [statusDays, setStatusDays] = useState(7);
  const [catDays, setCatDays] = useState(7);
  const [heatDays, setHeatDays] = useState(7);
  const byStatus = data.by_status as AnyRecord | undefined;
  const total = toNumber(data.total_copies);
  const statusItems = copyStatusKeys.map((key) => ({ name: statusLabel(key), value: toNumber(byStatus?.[key]) }));
  const categoryRows = asArray<AnyRecord>((data.category_health as AnyRecord | undefined)?.items).map((item) => ({ name: categoryLabel(item.category_id), count: toNumber(item.copy_count) })).sort((a, b) => b.count - a.count).slice(0, 8);
  const shelfRows = asArray<AnyRecord>((data.shelf_utilization as AnyRecord | undefined)?.items).slice(0, 8);
  const heatRows = shelfRows.map((item, index) => ({ zone: String(item.zone_code ?? item.zone_id ?? `Z${String(index + 1).padStart(2, "0")}`), label: String(item.zone_name ?? item.zone_label ?? "馆藏分区"), inRack: toNumber(item.in_rack_rate), useRate: toNumber(item.use_rate), staleRate: toNumber(item.stale_rate) }));
  const statusTotal = statusItems.reduce((sum, item) => sum + item.value, 0) || total;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[0.92fr_1.08fr]">
        <CompactCard title="馆藏状态分布" actions={<RangeButton days={statusDays} onChange={setStatusDays} />} bodyClassName="px-6 pb-4 pt-3">
          <div className="grid min-h-[206px] grid-cols-[minmax(0,245px)_minmax(260px,1fr)] items-center gap-4">
            <DonutCenterChart option={simpleDonutOption(statusItems)} height={202} centerTitle="总册数" centerValue={`${formatNumber(statusTotal)} 册`} centerLeft="50%" centerTop="52%" />
            <div className="space-y-2">{statusItems.map((item, index) => (<div key={item.name} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-2xl bg-[#f8fbff] px-4 py-2.5 text-[14px] font-black text-[#16213d]"><span className="flex min-w-0 items-center gap-3 truncate"><i className={`h-3.5 w-3.5 shrink-0 rounded-full ${statusColorClasses[index % statusColorClasses.length]}`} />{item.name}</span><span className="whitespace-nowrap">{formatNumber(item.value)} 册 <em className="not-italic text-[#64708b]">({percent(item.value, statusTotal)})</em></span></div>))}<div className="pt-1 text-center text-sm font-bold text-[#64708b]">统计口径：实体副本（Copy）状态</div></div>
          </div>
        </CompactCard>
        <CompactCard title="重点分类馆藏分布" actions={<RangeButton days={catDays} onChange={setCatDays} />} bodyClassName="px-6 pb-4 pt-3"><InlineChart option={barOption(categoryRows, "name", "count")} height={210} /></CompactCard>
      </div>
      <CompactCard title="馆藏分区健康热力图" actions={<RangeButton days={heatDays} onChange={setHeatDays} />} bodyClassName="px-6 pb-3 pt-3">
        <HealthGrid rows={heatRows} />
      </CompactCard>
    </div>
  );
}

export function HotColdTab({ data, collectionData }: { data: AnyRecord; collectionData: AnyRecord; loading: boolean }) {
  const [hotDays, setHotDays] = useState(7);
  const [coldDays, setColdDays] = useState(7);
  const [bubbleDays, setBubbleDays] = useState(7);
  const hotBooks = asArray<AnyRecord>(data.top_hot_books).slice(0, 5);
  const coldBooks = asArray<AnyRecord>(data.top_cold_books).slice(0, 5);
  const totalBooks = toNumber(collectionData.total_books);
  const categoryHeatRows = asArray<AnyRecord>((data.category_heat_distribution as AnyRecord | undefined)?.items);
  const fallbackCategoryRows = asArray<AnyRecord>((collectionData.category_health as AnyRecord | undefined)?.items);
  const bubbleSource = (categoryHeatRows.length ? categoryHeatRows : fallbackCategoryRows).slice(0, 8);
  const maxCopies = Math.max(...bubbleSource.map((item) => toNumber(item.copy_count)), 1);
  const maxBorrow = Math.max(...bubbleSource.map((item) => toNumber(item.borrow_90d)), 1);
  const bubbleRows = bubbleSource.map((item) => { const copies = toNumber(item.copy_count); const borrow = toNumber(item.borrow_90d); const hot = toNumber(item.hot_count); const cold = toNumber(item.cold_count); const sizeBase = Math.max(hot + cold, toNumber(item.book_count)); return { name: String(item.name ?? categoryLabel(item.category_id)), copies, borrow, hot, cold, size: 34 + Math.round((sizeBase / Math.max(totalBooks, sizeBase, 1)) * 180) + Math.round((copies / maxCopies) * 18) + Math.round((borrow / maxBorrow) * 16) }; });
  const hotTotal = toNumber(collectionData.hot_books); const coldTotal = toNumber(collectionData.cold_books);
  const hotBorrowTotal = hotBooks.reduce((sum, item) => sum + toNumber(item.borrow_90d), 0);
  const coldLongUnborrowed = coldBooks.filter((item) => toNumber(item.days_since_last_borrow) >= 180).length;
  const summaryCards = [
    { title: "热门图书", value: formatNumber(hotTotal), unit: "种", icon: "trend", tone: "red" as const, sub: `占馆藏图书 ${formatPercent(totalBooks ? hotTotal / totalBooks : 0)}` },
    { title: "冷门图书", value: formatNumber(coldTotal), unit: "种", icon: "available", tone: "blue" as const, sub: `占馆藏图书 ${formatPercent(totalBooks ? coldTotal / totalBooks : 0)}` },
    { title: "热门借阅次数", value: formatNumber(hotBorrowTotal), unit: "次", icon: "borrow", tone: "green" as const, sub: "当前热门榜近 90 天合计" },
    { title: "冷门长期未借", value: formatNumber(coldLongUnborrowed), unit: "种", icon: "catalog", tone: "orange" as const, sub: "当前冷门榜 180 天以上" },
  ];
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1fr_1.18fr]">
        <BookRankingPanel title="热门书排行" tone="hot" rows={hotBooks} valueKey="borrow_90d" extraKey="reserve_90d" empty="暂无热门书数据" rangeDays={hotDays} onRangeChange={setHotDays} />
        <BookRankingPanel title="冷门书排行" tone="cold" rows={coldBooks} valueKey="borrow_365d" extraKey="days_since_last_borrow" empty="暂无冷门书数据" rangeDays={coldDays} onRangeChange={setColdDays} />
        <CompactCard title="分类冷热分布" actions={<RangeButton days={bubbleDays} onChange={setBubbleDays} />} bodyClassName="px-5 pb-2 pt-1" className="h-[468px]"><InlineChart option={hotColdBubbleOption(bubbleRows)} height={376} /></CompactCard>
      </div>
      <CompactCard title="热门冷门概览" bodyClassName="p-3" className="h-[201px]"><div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{summaryCards.map((card) => <HotColdSummaryCard key={card.title} {...card} />)}</div></CompactCard>
    </div>
  );
}

export function ReadersTab({ data, circulationData }: { data: AnyRecord; circulationData: AnyRecord; collectionData: AnyRecord; loading: boolean }) {
  const [typeDays, setTypeDays] = useState(7);
  const [creditDays, setCreditDays] = useState(7);
  const [trendDays, setTrendDays] = useState(30);
  const [activityDays, setActivityDays] = useState(7);
  const [overdueDays, setOverdueDays] = useState(7);
  const [prefDays, setPrefDays] = useState(7);
  const typeItems = asArray<AnyRecord>((data.reader_type_distribution as AnyRecord | undefined)?.items).map((item) => ({ name: readerTypeLabel(item.name), value: toNumber(item.count), count: toNumber(item.count) })).filter((item) => item.count >= 0);
  const typeTotal = typeItems.reduce((sum, item) => sum + item.count, 0) || toNumber(data.registered_reader_count);
  const creditItems = asArray<AnyRecord>((data.credit_score_distribution as AnyRecord | undefined)?.items).map((item) => ({ name: creditBucketLabel(item.name), count: toNumber(item.count) })).sort((a, b) => creditBucketOrder(a.name) - creditBucketOrder(b.name));
  const readerTrend = data.reader_activity_trend as AnyRecord | undefined;
  const rawLabels = asArray<string>(readerTrend?.labels);
  const windowSize = Math.min(trendDays, rawLabels.length);
  const slicedLabels = rawLabels.slice(Math.max(0, rawLabels.length - windowSize));
  const trendLabels = slicedLabels.map((item) => item.slice(5) || item);
  const rawSeries = asArray<{ name: string; data: number[] }>(readerTrend?.series);
  const slicedSeries = rawSeries.map((s) => ({ ...s, data: asArray<number>(s.data).slice(Math.max(0, (s.data?.length || 0) - windowSize)) }));
  const activeTrend = asArray<number>(slicedSeries.find((item) => item.name === "active_readers")?.data).map((value) => toNumber(value));
  const newTrend = asArray<number>(slicedSeries.find((item) => item.name === "new_readers")?.data).map((value) => toNumber(value));
  const activityRows = (() => { const rows = asArray<AnyRecord>(data.activity_levels); if (rows.length) return rows.map((row, index) => ({ name: activityLevelLabel(row.name ?? row.label, index), count: toNumber(row.count), percent: toNumber(row.percent) })); const registered = toNumber(data.registered_reader_count); const active = toNumber(data.monthly_active_reader_count); const suspended = toNumber(data.suspended_count); const sleeping = Math.max(registered - active - suspended, 0); return [{ name: activityLevelLabels[0], count: toNumber((data.top_active_readers as AnyRecord[] | undefined)?.length), percent: 0 }, { name: activityLevelLabels[1], count: Math.max(active - toNumber((data.top_active_readers as AnyRecord[] | undefined)?.length), 0), percent: 0 }, { name: activityLevelLabels[2], count: Math.max(active - Math.round(active * 0.62), 0), percent: 0 }, { name: activityLevelLabels[3], count: sleeping, percent: 0 }]; })();
  const activityRowsForFunnel = activityRows.map((row) => ({ name: row.name, value: row.count }));
  const preferenceRows = asArray<AnyRecord>((data.reader_preference_top5 as AnyRecord | undefined)?.items).concat(asArray<AnyRecord>((circulationData.category_heat_distribution as AnyRecord | undefined)?.items)).map((row) => ({ name: String(row.name ?? categoryLabel(row.category_id)), count: toNumber(row.borrow_count ?? row.borrow_90d), percent: toNumber(row.percent) })).filter((row) => row.name && row.count > 0).sort((a, b) => b.count - a.count).slice(0, 5);
  const statCards = [
    { title: "注册读者总数", value: formatNumber(data.registered_reader_count), unit: "人", icon: "readers", tone: "blue" as const },
    { title: "近 30 天活跃读者", value: formatNumber(data.monthly_active_reader_count), unit: "人", icon: "success", tone: "green" as const },
    { title: "信用受限读者", value: formatNumber(data.credit_limited_count ?? (data.credit_buckets as AnyRecord | undefined)?.mid), unit: "人", icon: "book", tone: "orange" as const },
    { title: "暂停借阅读者", value: formatNumber(data.suspended_count), unit: "人", icon: "overdue", tone: "purple" as const },
  ];
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">{statCards.map((card) => <StatCard key={card.title} {...card} compact />)}</div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.12fr_0.88fr_1.3fr]">
        <CompactCard title="读者类型分布" actions={<RangeButton days={typeDays} onChange={setTypeDays} />} bodyClassName="px-5 pb-2 pt-2" className="h-[238px]">
          <div className="grid h-[164px] grid-cols-[minmax(0,132px)_minmax(0,1fr)] items-center gap-3">
            <DonutCenterChart option={simpleDonutOption(typeItems, ["50%", "52%"])} height={148} centerTitle="总人数" centerValue={`${formatNumber(typeTotal)}人`} centerLeft="50%" centerTop="52%" />
            <div className="space-y-1.5">{typeItems.map((item, index) => (<div key={item.name} className="grid grid-cols-[minmax(0,1fr)_48px_52px] items-center gap-1.5 text-[11px] font-black text-[#17213c]"><span className="flex min-w-0 items-center gap-1.5 truncate"><i className={`h-2.5 w-2.5 shrink-0 rounded-full ${statusColorClasses[index % statusColorClasses.length]}`} />{item.name}</span><span className="whitespace-nowrap text-right">{formatNumber(item.count)}</span><span className="whitespace-nowrap text-right text-[#64708b]">{percent(item.count, typeTotal)}</span></div>))}</div>
          </div>
        </CompactCard>
        <CompactCard title="信用分布" actions={<RangeButton days={creditDays} onChange={setCreditDays} />} bodyClassName="px-4 pb-2 pt-2" className="h-[238px]"><InlineChart option={creditScoreOption(creditItems)} height={164} /></CompactCard>
        <CompactCard title="读者活跃趋势" actions={<RangeButton days={trendDays} onChange={setTrendDays} />} bodyClassName="px-5 pb-2 pt-2" className="h-[238px]"><InlineChart option={readerTrendOption(trendLabels, newTrend, activeTrend)} height={164} /></CompactCard>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.18fr_1.08fr_1.2fr]">
        <CompactCard title="读者借阅活跃度分层" actions={<RangeButton days={activityDays} onChange={setActivityDays} />} bodyClassName="px-5 pb-2 pt-2" className="h-[311px]">
          <ReaderActivityLevelChart rows={activityRowsForFunnel} />
        </CompactCard>
        <CompactCard title="逾期读者排行" actions={<RangeButton days={overdueDays} onChange={setOverdueDays} />} bodyClassName="px-4 pb-2 pt-2" className="h-[311px]">
          {(() => { const overdueRows = asArray<AnyRecord>(data.readers_with_overdue_risk).slice(0, 5); const maxVal = Math.max(...overdueRows.map((row) => toNumber(row.overdue_days ?? row.overdue_count)), 1); return (<div className="space-y-1"><div className="grid grid-cols-[26px_minmax(0,1fr)_46px_34px] gap-2 text-[10.5px] font-black text-[#66708a]"><span>排名</span><span>读者</span><span className="text-right">天数</span><span className="text-right">册数</span></div>{overdueRows.map((row, index) => { const days = toNumber(row.overdue_days ?? row.overdue_count); return (<div key={String(row.reader_code ?? index)} className="grid grid-cols-[26px_minmax(0,1fr)_46px_34px] items-center gap-2 text-[11px] font-black text-[#17213c]"><span className="grid h-5 w-5 place-items-center rounded-full bg-[#eaf1ff] text-[10px] text-[var(--bf-brand)]">{index + 1}</span><span className="min-w-0"><span className="block truncate">{String(row.name ?? row.reader_code ?? "-")}</span><span className="mt-0.5 block h-1.5 rounded-full bg-[#edf2f8]"><i className="block h-1.5 rounded-full bg-[var(--bf-brand)]" style={{ width: `${Math.max(12, (days / maxVal) * 100)}%` }} /></span></span><span className="whitespace-nowrap text-right">{formatNumber(days)}天</span><span className="whitespace-nowrap text-right">{formatNumber(row.overdue_count)}册</span></div>); })}{!overdueRows.length ? <div className="py-12 text-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无逾期读者</div> : null}</div>); })()}
        </CompactCard>
        <CompactCard title="读者偏好 TOP5" actions={<RangeButton days={prefDays} onChange={setPrefDays} />} bodyClassName="px-4 pb-2 pt-2" className="h-[311px]">
          {(() => { const maxVal = Math.max(...preferenceRows.map((row) => row.count), 1); const total = preferenceRows.reduce((sum, row) => sum + row.count, 0); return (<div className="space-y-1"><div className="grid grid-cols-[26px_minmax(0,1fr)_60px_42px] gap-2 text-[10.5px] font-black text-[#66708a]"><span>排名</span><span>类别</span><span className="text-right">借阅册数</span><span className="text-right">占比</span></div>{preferenceRows.map((row, index) => { const ratio = Number.isFinite(Number(row.percent)) && Number(row.percent) > 0 ? ratioValue(row.percent) : total ? row.count / total : 0; return (<div key={row.name} className="grid grid-cols-[26px_minmax(0,1fr)_60px_42px] items-center gap-2 text-[11px] font-black text-[#17213c]"><span>{index + 1}</span><span className="min-w-0"><span className="block truncate">{row.name}</span><span className="mt-0.5 block h-1.5 rounded-full bg-[#edf2f8]"><i className="block h-1.5 rounded-full bg-[var(--bf-brand)]" style={{ width: `${Math.max(12, (row.count / maxVal) * 100)}%` }} /></span></span><span className="whitespace-nowrap text-right">{formatNumber(row.count)}</span><span className="whitespace-nowrap text-right">{(ratio * 100).toFixed(1)}%</span></div>); })}{!preferenceRows.length ? <div className="py-12 text-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无偏好数据</div> : null}</div>); })()}
        </CompactCard>
      </div>
    </div>
  );
}

export function AITab({ data }: { data: AnyRecord; loading: boolean }) {
  const [aiTrendDays, setAiTrendDays] = useState(7);
  const [toolDays, setToolDays] = useState(7);
  const [transferDays, setTransferDays] = useState(7);
  const [bizDays, setBizDays] = useState(7);
  const total = toNumber(data.total_ai_runs ?? data.total_runs);
  const successRate = ratioValue(data.success_rate);
  const transferRate = ratioValue(data.transfer_rate, total ? (toNumber(data.failed_count) + toNumber(data.waiting_authorization_count)) / total : 0);
  const averageMinutes = toNumber(data.average_processing_minutes);
  const averageSeconds = toNumber(data.average_processing_seconds) || averageMinutes * 60;
  const toolItems = asArray<AnyRecord>((data.tool_usage_rank as AnyRecord | undefined)?.items).map((item) => ({ name: aiDisplayName(item.tool_name ?? item.name), value: toNumber(item.count ?? item.value), count: toNumber(item.count ?? item.value) })).filter((item) => item.count > 0);
  const businessItems = asArray<AnyRecord>((data.business_type_distribution as AnyRecord | undefined)?.items).map((item) => ({ name: aiDisplayName(item.name ?? item.tool_name), value: toNumber(item.count ?? item.value), count: toNumber(item.count ?? item.value) })).filter((item) => item.count > 0);
  const transferItems = asArray<AnyRecord>((data.transfer_reason_distribution as AnyRecord | undefined)?.items).map((item) => ({ name: aiDisplayName(item.name ?? item.status), count: toNumber(item.count ?? item.value) })).filter((item) => item.count > 0);
  const statCards = [
    { title: "AI 任务总数", value: formatNumber(total), unit: "条", icon: "ai", tone: "blue" as const, trend: total ? "来自真实 AI 运行 / 复核记录" : "暂无真实记录" },
    { title: "AI 成功率", value: formatPercent(successRate), icon: "success", tone: "green" as const, trend: "按真实状态统计" },
    { title: "平均处理时长", value: formatDuration(averageSeconds), icon: "calendar", tone: "orange" as const, trend: "按开始/完成时间计算" },
    { title: "转人工率", value: formatPercent(transferRate), icon: "readers", tone: "red" as const, trend: `${formatNumber(toNumber(data.waiting_authorization_count))} 条待处理` },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-4">{statCards.map((card) => <StatCard key={card.title} {...card} compact />)}</div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <CompactCard title="AI 成功率趋势" actions={<RangeButton days={aiTrendDays} onChange={setAiTrendDays} />} bodyClassName="px-5 pb-4 pt-3" className="h-[270px]"><InlineChart option={aiTrendOption(data.daily_efficiency_trend as AnyRecord | undefined)} height={190} /></CompactCard>
        <CompactCard title="AI 工具调用分布" actions={<RangeButton days={toolDays} onChange={setToolDays} />} bodyClassName="px-5 pb-4 pt-3" className="h-[270px]">
          {toolItems.filter((item) => item.value > 0).length ? (
            <div className="grid h-[190px] grid-cols-[minmax(0,230px)_minmax(250px,1fr)] items-center gap-4"><DonutCenterChart option={aiPieOption(toolItems)} height={186} centerTitle="总调用次数" centerValue={`${formatNumber(toolItems.reduce((sum, item) => sum + item.value, 0))} 次`} centerLeft="32%" centerTop="52%" /><div className="space-y-2">{toolItems.filter((item) => item.value > 0).slice(0, 7).map((item, index) => { const sum = toolItems.reduce((acc, i) => acc + i.value, 0); const colors = ["bg-blue-600", "bg-green-500", "bg-amber-500", "bg-violet-500", "bg-cyan-500", "bg-rose-500", "bg-slate-500"]; return (<div key={item.name} className="grid grid-cols-[minmax(0,1fr)_72px_54px] items-center gap-3 text-[13px] font-black text-[#17213c]"><span className="flex min-w-0 items-center gap-2 truncate"><i className={`h-3 w-3 shrink-0 rounded-full ${colors[index % colors.length]}`} />{item.name}</span><span className="whitespace-nowrap text-right">{formatNumber(item.value)} 次</span><span className="whitespace-nowrap text-right text-[#64708b]">{percent(item.value, sum)}</span></div>); })}</div></div>
          ) : (<div className="grid h-[190px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无真实 AI 统计数据</div>)}
        </CompactCard>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <CompactCard title="转人工原因分布" actions={<RangeButton days={transferDays} onChange={setTransferDays} />} bodyClassName="px-5 pb-4 pt-3" className="h-[270px]"><InlineChart option={aiHorizontalBarOption(transferItems)} height={190} /></CompactCard>
        <CompactCard title="AI 处理业务类型占比" actions={<RangeButton days={bizDays} onChange={setBizDays} />} bodyClassName="px-5 pb-4 pt-3" className="h-[270px]">
          {(businessItems.length ? businessItems : toolItems).filter((item) => item.value > 0).length ? (
            <div className="grid h-[190px] grid-cols-[minmax(0,230px)_minmax(250px,1fr)] items-center gap-4"><DonutCenterChart option={aiPieOption(businessItems.length ? businessItems : toolItems)} height={186} centerTitle="总任务数" centerValue={`${formatNumber((businessItems.length ? businessItems : toolItems).reduce((sum, item) => sum + item.value, 0))} 次`} centerLeft="32%" centerTop="52%" /><div className="space-y-2">{(businessItems.length ? businessItems : toolItems).filter((item) => item.value > 0).slice(0, 7).map((item, index) => { const sum = (businessItems.length ? businessItems : toolItems).reduce((acc, i) => acc + i.value, 0); const colors = ["bg-blue-600", "bg-green-500", "bg-amber-500", "bg-violet-500", "bg-cyan-500", "bg-rose-500", "bg-slate-500"]; return (<div key={item.name} className="grid grid-cols-[minmax(0,1fr)_72px_54px] items-center gap-3 text-[13px] font-black text-[#17213c]"><span className="flex min-w-0 items-center gap-2 truncate"><i className={`h-3 w-3 shrink-0 rounded-full ${colors[index % colors.length]}`} />{item.name}</span><span className="whitespace-nowrap text-right">{formatNumber(item.value)} 次</span><span className="whitespace-nowrap text-right text-[#64708b]">{percent(item.value, sum)}</span></div>); })}</div></div>
          ) : (<div className="grid h-[190px] place-items-center text-sm font-semibold text-[var(--bf-text-secondary)]">暂无真实 AI 统计数据</div>)}
        </CompactCard>
      </div>
    </div>
  );
}
