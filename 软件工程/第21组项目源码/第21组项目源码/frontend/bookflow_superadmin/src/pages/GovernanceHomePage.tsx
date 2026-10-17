import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { ErrorState, SkeletonBlock } from "@/components/ui/States";
import { ResultTag } from "@/components/ui/SuperAdminUI";
import { superAdminApi, type GovernanceOverview, type KpiValue } from "@/api/superAdmin";
import { formatDateTime, formatNumber } from "@common/utils/format";

const metricCards: Array<{ key: keyof GovernanceOverview["kpis"]; label: string; icon: AppIconName; tone: string }> = [
  { key: "totalBooks", label: "图书总数", icon: "document", tone: "#e8f1ff" },
  { key: "totalCopies", label: "馆藏副本", icon: "data", tone: "#efe9ff" },
  { key: "readersTotal", label: "读者总数", icon: "user", tone: "#e5f8fb" },
  { key: "currentBorrowed", label: "当前借出", icon: "readers", tone: "#fff1dd" },
  { key: "todayBorrow", label: "今日借阅", icon: "check", tone: "#e6f8ef" },
  { key: "todayReturn", label: "今日归还", icon: "tasks", tone: "#e8f1ff" },
  { key: "reservationCount", label: "预约数量", icon: "bell", tone: "#efe9ff" },
  { key: "overdueCount", label: "逾期数量", icon: "close", tone: "#fee8e8" },
];

function MetricCard({ label, value, icon, tone }: { label: string; value: KpiValue; icon: AppIconName; tone: string }) {
  const delta = Number(value.delta || 0);
  const isUp = delta >= 0;
  return (
    <div className="flex min-w-[130px] flex-1 items-center justify-center gap-3 border-r border-[#dfe8f5] px-3 py-3 last:border-r-0">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[#1769f7]" style={{ backgroundColor: tone }}>
        <AppIcon name={icon} size={22} />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[12px] font-black text-[#4e5e78]">{label}</div>
        <div className="mt-0.5 truncate text-[22px] font-black leading-none text-[#071434]">{formatNumber(value.value)}</div>
        <div className={`mt-1 truncate text-[11px] font-bold ${isUp ? "text-[#1769f7]" : "text-[#12a976]"}`}>
          较昨日 {isUp ? "↑" : "↓"} {formatNumber(Math.abs(delta))}
        </div>
      </div>
    </div>
  );
}

function TrendChart({ data }: { data: GovernanceOverview["borrowReturnTrend"] }) {
  const width = 720;
  const height = 230;
  const max = Math.max(1, ...data.flatMap((item) => [item.borrow, item.return]));
  const xStep = data.length > 1 ? width / (data.length - 1) : width;
  const point = (value: number, index: number) => `${index * xStep},${height - (value / max) * (height - 28) - 16}`;
  const borrowPoints = data.map((item, index) => point(item.borrow, index)).join(" ");
  const returnPoints = data.map((item, index) => point(item.return, index)).join(" ");
  const areaPoints = `0,${height - 16} ${returnPoints} ${width},${height - 16}`;

  return (
    <div className="h-[300px]">
      <div className="mb-3 flex items-center justify-end gap-5 text-[12px] font-black text-[#52617d]">
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full bg-[#1769f7]" />借阅量</span>
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full bg-[#13c096]" />归还量</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height + 36}`} className="h-[250px] w-full overflow-visible" role="img" aria-label="近 7 日借阅归还趋势">
        <defs>
          <linearGradient id="returnArea" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#13c096" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#13c096" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <line key={tick} x1="0" x2={width} y1={16 + tick * (height - 28)} y2={16 + tick * (height - 28)} stroke="#dce6f4" strokeDasharray="4 5" />
        ))}
        <polygon points={areaPoints} fill="url(#returnArea)" />
        <polyline points={borrowPoints} fill="none" stroke="#1769f7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points={returnPoints} fill="none" stroke="#13c096" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((item, index) => (
          <g key={item.date}>
            <text x={index * xStep} y={height + 22} textAnchor="middle" fill="#60708c" fontSize="13" fontWeight="700">
              {item.date}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function Donut({ items }: { items: GovernanceOverview["copyStatusDistribution"] }) {
  const total = items.reduce((sum, item) => sum + Number(item.value || 0), 0);
  const palette = ["#7c3aed", "#f97316", "#e11d48", "#d97706", "#0891b2", "#475569"];
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  let cursor = 0;
  const stops = items.map((item, index) => {
    const start = cursor;
    cursor += total ? (item.value / total) * 100 : 0;
    return `${palette[index % palette.length]} ${start}% ${cursor}%`;
  });
  return (
    <div className="flex h-[300px] flex-col items-center justify-start pt-8 gap-2">
      <div
        className="relative h-[240px] w-[240px] shrink-0 rounded-full"
        style={{ background: total ? `conic-gradient(${stops.join(",")})` : "#eef2f7" }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const cx = rect.width / 2, cy = rect.height / 2;
          const x = e.clientX - rect.left - cx, y = e.clientY - rect.top - cy;
          let angle = Math.atan2(y, x) * (180 / Math.PI) + 90;
          if (angle < 0) angle += 360;
          const pct = (angle / 360) * 100;
          let acc = 0;
          for (let i = 0; i < items.length; i++) {
            const seg = items[i];
            const segPct = total ? (Number(seg.value || 0) / total) * 100 : 0;
            if (pct >= acc && pct <= acc + segPct) { setHoveredIndex(i); break; }
            acc += segPct;
          }
        }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        <div className="absolute inset-[58px] flex flex-col items-center justify-center rounded-full bg-white">
          <strong className="text-[38px] font-black text-[#071434]">{formatNumber(total)}</strong>
          <span className="text-[15px] font-black text-[#6a7892]">馆藏副本</span>
        </div>
      </div>
      {hoveredIndex !== null ? (
        <div className="flex items-center gap-2 rounded-[6px] bg-[#071434] px-3 py-1.5 text-white">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: palette[hoveredIndex % palette.length] }} />
          <span className="text-[12px] font-black">{items[hoveredIndex].label}</span>
          <span className="text-[12px] font-black opacity-70">{formatNumber(items[hoveredIndex].value)}</span>
        </div>
      ) : (
        <div className="h-[26px]" />
      )}
    </div>
  );
}

function resolveAssetUrl(src?: string) {
  const value = String(src || "").trim();
  if (!value) return "";
  if (/^https?:\/\//i.test(value)) return value;
  const apiBase = String(import.meta.env.VITE_API_BASE_URL || "").trim();
  if (value.startsWith("/uploads") && /^https?:\/\//i.test(apiBase)) {
    return `${new URL(apiBase).origin}${value}`;
  }
  return value;
}

function BookCover({ src, title }: { src?: string; title: string }) {
  const [failed, setFailed] = useState(false);
  const resolved = resolveAssetUrl(src);
  if (resolved && !failed) return <img className="h-12 w-9 rounded-[4px] object-cover shadow-sm ring-1 ring-[#dbe5f2]" src={resolved} alt={title} onError={() => setFailed(true)} />;
  return (
    <span className="flex h-12 w-9 items-center justify-center rounded-[4px] bg-gradient-to-b from-[#e7eef9] to-[#f8fbff] text-[#8a9ab4] ring-1 ring-[#dbe5f2]">
      <AppIcon name="document" size={18} />
    </span>
  );
}

export function GovernanceHomePage() {
  const overview = useQuery({ queryKey: ["super-admin", "overview"], queryFn: superAdminApi.governanceOverview });
  const [readerHovered, setReaderHovered] = useState(false);

  if (overview.isLoading) {
    return (
      <div className="bf-super-page">
        <SkeletonBlock className="h-[150px]" />
        <div className="grid grid-cols-[1.2fr_0.7fr_0.55fr] gap-3">
          <SkeletonBlock className="h-[330px]" />
          <SkeletonBlock className="h-[330px]" />
          <SkeletonBlock className="h-[330px]" />
        </div>
      </div>
    );
  }
  if (overview.isError || !overview.data) return <ErrorState onRetry={() => overview.refetch()} />;

  const data = overview.data;
  return (
    <div className="bf-super-page">
      <section className="bf-super-card grid grid-cols-4 overflow-hidden xl:grid-cols-8">
        {metricCards.map((card) => (
          <MetricCard key={card.key} label={card.label} value={data.kpis[card.key]} icon={card.icon} tone={card.tone} />
        ))}
      </section>

      <div className="grid grid-cols-[minmax(0,1.25fr)_minmax(320px,0.67fr)_minmax(260px,0.55fr)] gap-3">
        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>近 7 日借阅 / 归还趋势</span>
          </div>
          <TrendChart data={data.borrowReturnTrend} />
        </section>

        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>馆藏状态分布</span>
          </div>
          <Donut items={data.copyStatusDistribution} />
        </section>

        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>热门图书 Top 5</span>
          </div>
          <div className="mt-4 grid gap-3">
            {data.hotBooks.length ? data.hotBooks.slice(0, 5).map((book) => (
              <div key={`${book.rank}-${book.book_id ?? book.title}`} className="grid grid-cols-[24px_38px_minmax(0,1fr)_auto] items-center gap-3">
                <span className={`flex h-6 w-6 items-center justify-center rounded-[5px] text-[12px] font-black text-white ${book.rank <= 3 ? "bg-[#f59e0b]" : "bg-[#c7d3e5] text-[#263653]"}`}>{book.rank}</span>
                <BookCover src={book.cover_url} title={book.title} />
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-black text-[#0f1f3a]">{book.title}</div>
                  <div className="truncate text-[12px] font-bold text-[#65728c]">{book.author || book.publisher || "-"}</div>
                </div>
                <span className="text-[12px] font-black text-[#1769f7]">借阅 {formatNumber(book.borrow_count)} 次</span>
              </div>
            )) : <div className="bf-empty-state min-h-[210px]">暂无热门图书数据</div>}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-[minmax(0,0.75fr)_minmax(0,0.85fr)_minmax(0,1.05fr)] gap-3">
        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>读者活跃概览</span>
          </div>
          <div className="mt-5 flex flex-col items-center justify-start pt-2 gap-2">
            <div
              className="relative h-[180px] w-[180px] shrink-0 rounded-full"
              style={{ background: `conic-gradient(#0891b2 ${data.readerActivity.active_ratio}%, #f97316 0)` }}
              onMouseEnter={() => setReaderHovered(true)}
              onMouseLeave={() => setReaderHovered(false)}
            >
              <div className="absolute inset-[44px] flex flex-col items-center justify-center rounded-full bg-white">
                <strong className="text-[34px] font-black text-[#071434]">{data.readerActivity.active_ratio}%</strong>
                <span className="text-[12px] font-black text-[#6a7892]">活跃读者占比</span>
              </div>
            </div>
            {readerHovered ? (
              <div className="flex items-center gap-2 rounded-[6px] bg-[#071434] px-3 py-1.5 text-white">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-[#0891b2]" />
                <span className="text-[12px] font-black">今日活跃 {formatNumber(data.readerActivity.today_active)}</span>
                <span className="text-[12px] font-black opacity-70">新增 {formatNumber(data.readerActivity.today_new)}</span>
                <span className="text-[12px] font-black opacity-70">总活跃 {formatNumber(data.readerActivity.active)}</span>
              </div>
            ) : (
              <div className="h-[26px]" />
            )}
          </div>
        </section>

        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>系统关键活动</span>
          </div>
          <div className="mt-4 grid gap-3">
            {data.systemActivities.slice(0, 5).map((item) => (
              <div key={item.id} className="grid grid-cols-[36px_minmax(0,1fr)_76px] items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#eef5ff] text-[#1769f7]">
                  <AppIcon name={item.kind === "login" ? "user" : "tasks"} size={18} />
                </span>
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-black text-[#172541]">{item.title}</div>
                  <div className="truncate text-[12px] font-bold text-[#64718d]">{item.actor} · {formatDateTime(item.created_at)}</div>
                </div>
                <ResultTag result={item.result} />
              </div>
            ))}
          </div>
        </section>

        <section className="bf-super-card p-5">
          <div className="bf-card-title">
            <span>系统健康状态</span>
          </div>
          <div className="mt-5 grid grid-cols-[82px_minmax(0,1fr)] items-center gap-6">
            <span className="flex h-20 w-20 items-center justify-center rounded-full bg-[#e6f8ef] text-[#12a976]">
              <AppIcon name="check" size={42} />
            </span>
            <div>
              <div className="text-[18px] font-black text-[#071434]">{data.systemHealth.status === "normal" ? "系统运行正常" : "系统需要关注"}</div>
              <div className="mt-1 text-[14px] font-bold text-[#64718d]">健康评分 {data.systemHealth.score}/100</div>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-4 gap-3">
            {data.systemHealth.services.map((service) => (
              <div key={service.key} className="rounded-[7px] border border-[#e5edf8] bg-[#fbfdff] px-3 py-3 text-center">
                <div className="truncate text-[12px] font-black text-[#64718d]">{service.label}</div>
                <div className={service.status === "normal" ? "mt-2 text-[13px] font-black text-[#12a976]" : "mt-2 text-[13px] font-black text-[#f59e0b]"}>
                  {service.text}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
