import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { catalogApi } from "@/api/catalog";
import { locationsApi } from "@/api/locations";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { formatNumber } from "@/utils/format";
import type { AnyRecord } from "@/types/api";
import type { Tone } from "@/utils/status";
import adminHomeHero from "@/assets/ai/admin-home-hero.png";
import adminHomeHeroSlide02 from "@/assets/ai/admin-home-hero-slide-02.png";
import adminHomeHeroSlide03 from "@/assets/ai/admin-home-hero-slide-03.png";
import adminHomeHeroSlide04 from "@/assets/ai/admin-home-hero-slide-04.png";
import adminHomeHeroSlide05 from "@/assets/ai/admin-home-hero-slide-05.png";
import rhythm from "@/styles/AdminRhythm.module.css";

const HERO_RATIO = "aspect-[5/1]";
const HERO_INTERVAL_MS = 4800;
const HERO_SLIDES = [
  { src: adminHomeHero, alt: "BookFlow 图书馆数字门厅" },
  { src: adminHomeHeroSlide02, alt: "BookFlow 数字门厅轮播图 2" },
  { src: adminHomeHeroSlide03, alt: "BookFlow 数字门厅轮播图 3" },
  { src: adminHomeHeroSlide04, alt: "BookFlow 数字门厅轮播图 4" },
  { src: adminHomeHeroSlide05, alt: "BookFlow 数字门厅轮播图 5" },
] as const;

type AICapability = {
  icon: AppIconName;
  text: string;
};

const aiCapabilities: AICapability[] = [
  { icon: "sparkles", text: "理解读者找书需求" },
  { icon: "catalog", text: "根据主题推荐馆藏" },
  { icon: "calendar", text: "解释借阅与预约规则" },
  { icon: "notifications", text: "辅助生成读者通知" },
  { icon: "data", text: "分析馆藏结构与借阅趋势" },
];

const themeTones: Tone[] = ["purple", "blue", "green", "orange", "cyan"];
const spaceTones: Tone[] = ["blue", "green", "purple", "orange", "cyan"];

function text(value: unknown, fallback = "-") {
  const result = String(value ?? "").trim();
  return result || fallback;
}

function num(value: unknown) {
  return Number(value ?? 0) || 0;
}

function categoryHref(row: AnyRecord) {
  const code = text(row.category_code, "");
  return code ? `/admin/catalog?category_code=${encodeURIComponent(code)}` : "/admin/catalog";
}

function SectionTitle({ icon, title, action }: { icon: AppIconName; title: string; action?: ReactNode }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#f0edff] text-[#6354f0]">
          <AppIcon name={icon} size={19} />
        </span>
        <h2 className="truncate text-[18px] font-black text-[#0b1533]">{title}</h2>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

function HeroBanner() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % HERO_SLIDES.length);
    }, HERO_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <section className={`bf-card ${HERO_RATIO} relative overflow-hidden`}>
      <div className="relative h-full w-full">
        {HERO_SLIDES.map((slide, index) => (
          <img
            key={slide.src}
            src={slide.src}
            alt={slide.alt}
            className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ease-out ${index === activeIndex ? "opacity-100" : "opacity-0"}`}
            draggable={false}
          />
        ))}
      </div>
      <div className="absolute bottom-4 right-5 z-10 flex items-center gap-2 rounded-full bg-white/70 px-2.5 py-1.5 shadow-[0_10px_24px_rgba(15,23,42,0.12)] backdrop-blur">
        {HERO_SLIDES.map((slide, index) => (
          <button
            key={slide.src}
            type="button"
            aria-label={`切换数字门厅轮播图 ${index + 1}`}
            onClick={() => setActiveIndex(index)}
            className={`h-2.5 rounded-full transition-all ${index === activeIndex ? "w-7 bg-[#5b4bf2]" : "w-2.5 bg-[#cbd5e1] hover:bg-[#94a3b8]"}`}
          />
        ))}
      </div>
    </section>
  );
}

function zoneHref(row: AnyRecord) {
  const code = text(row.zone_code, "");
  return code ? `/admin/catalog?zone_code=${encodeURIComponent(code)}` : "/admin/catalog";
}

function SpaceCard({ item, index }: { item: AnyRecord; index: number }) {
  const floor = text(item.floor, "未设置楼层");
  const name = text(item.zone_name ?? item.name, "未命名空间");
  const use = text(item.main_use ?? item.purpose, "");
  const code = text(item.zone_code, "");
  const area = num(item.area_sqm);
  const tone = spaceTones[index % spaceTones.length];

  return (
    <Link to={zoneHref(item)} className="group flex min-h-[74px] items-center gap-3 rounded-[10px] border border-[#e7ecf5] bg-[#fbfcff] px-3.5 py-3 transition hover:border-[#cfc8ff] hover:bg-white">
      <FeatureIcon name="catalog" tone={tone} size="sm" className="h-10 w-10 rounded-[10px]" />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-[13px] font-black text-[#0b1533]">{floor}</span>
          <span className="min-w-0 truncate text-[14px] font-black text-[#334155]">{name}</span>
        </div>
        <div className="mt-1 flex min-w-0 items-center gap-2 text-[12px] font-bold text-[#64748b]">
          {code ? <span className="shrink-0">{code}</span> : null}
          {use ? <span className="truncate">{use}</span> : null}
          {area > 0 ? <span className="shrink-0">{formatNumber(area)} 平方米</span> : null}
        </div>
      </div>
      <AppIcon name="right" size={18} className="text-[#94a3b8] transition group-hover:text-[#6354f0]" />
    </Link>
  );
}

function AiHelpPanel() {
  return (
    <section className="bf-card p-6">
      <SectionTitle icon="ai" title="BookFlow AI 可以帮你" action={<Link to="/admin/ai" className="text-[13px] font-black text-[#6354f0] hover:text-[#4f46e5]">进入工作台</Link>} />
      <div className="mt-11 grid grid-cols-2 gap-3">
        {aiCapabilities.map((item) => (
          <Link key={item.text} to="/admin/ai" className="flex h-10 items-center justify-center gap-2 rounded-full bg-[#f6f7fb] px-4 text-[13px] font-bold text-[#475569] transition hover:bg-[#eeeaff] hover:text-[#5b4bf2]">
            <AppIcon name={item.icon} size={16} />
            <span className="truncate">{item.text}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function CategoryThemeCard({ row, index }: { row: AnyRecord; index: number }) {
  const tone = themeTones[index % themeTones.length];
  const code = text(row.category_code, "");
  const name = text(row.category_name, "未命名主题");

  return (
    <Link
      to={categoryHref(row)}
      className="group flex h-[52px] w-[176px] shrink-0 snap-start items-center gap-2.5 rounded-[10px] border border-[#e7ecf5] bg-white px-3 shadow-[0_8px_18px_rgba(15,23,42,0.032)] transition hover:-translate-y-0.5 hover:border-[#cfc8ff] hover:shadow-[0_14px_28px_rgba(91,75,242,0.09)]"
    >
      <FeatureIcon name="catalog" tone={tone} size="sm" className="h-8 w-8 shrink-0 rounded-[8px]" />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 truncate text-[13px] font-black text-[#0b1533]">{name}</span>
          {code ? <span className="shrink-0 rounded-full bg-[#f5f7fb] px-2 py-0.5 text-[11px] font-black text-[#64748b]">{code}</span> : null}
        </div>
      </div>
    </Link>
  );
}

export function HomePage() {
  const categoriesQuery = useQuery({ queryKey: ["catalog", "categories", "home"], queryFn: () => catalogApi.categories({ limit: 12, offset: 0 }) });
  const spacesQuery = useQuery({ queryKey: ["locations", "zones", "home"], queryFn: () => locationsApi.zones({ limit: 20, offset: 0 }) });

  const categories: AnyRecord[] = categoriesQuery.data?.items ?? [];
  const totalCategories = Number(categoriesQuery.data?.total ?? categories.length);
  const spaces: AnyRecord[] = (spacesQuery.data?.items ?? []).sort((a, b) => {
    const fa = String(a.floor ?? "");
    const fb = String(b.floor ?? "");
    const na = parseInt(fa.replace(/[^0-9-]/g, ""), 10) || 0;
    const nb = parseInt(fb.replace(/[^0-9-]/g, ""), 10) || 0;
    if (na !== nb) return na - nb;
    return fa.localeCompare(fb);
  });

  return (
    <div className={`${rhythm.scrollPage} ${rhythm.homePage}`}>
      <HeroBanner />

      <div className="grid items-start gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="bf-card p-6">
          <SectionTitle icon="home" title="馆藏空间" action={<Link to="/admin/catalog" className="text-[13px] font-black text-[#6354f0] hover:text-[#4f46e5]">查看馆藏</Link>} />
          {spacesQuery.isLoading ? (
            <div className="mt-5 grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <SkeletonBlock key={index} className="h-[74px]" />
              ))}
            </div>
          ) : spacesQuery.isError ? (
            <div className="mt-5 flex h-24 items-center justify-center rounded-[10px] border border-[#fee2e2] bg-[#fff7f7] text-[14px] font-bold text-[#dc2626]">
              馆藏空间加载失败。
            </div>
          ) : spaces.length > 0 ? (
            <div className="mt-5 max-h-[168px] overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              <div className="grid grid-cols-2 gap-3">
                {spaces.map((item, index) => (
                  <SpaceCard key={String(item.id ?? item.zone_code ?? index)} item={item} index={index} />
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-5 flex h-24 items-center justify-center rounded-[10px] border border-[#e7ecf5] bg-[#fbfcff] text-[14px] font-bold text-[#64748b]">
              暂无馆藏空间配置。
            </div>
          )}
        </section>

        <AiHelpPanel />
      </div>

      <section className={`bf-card min-w-0 overflow-hidden px-5 py-4 ${rhythm.homeThemesCard}`}>
        <SectionTitle
          icon="catalog"
          title="馆藏主题"
          action={<span className="text-[13px] font-bold text-[#64748b]">一级分类 · 共 {formatNumber(totalCategories)} 个</span>}
        />
        {categoriesQuery.isError ? (
          <div className="mt-3 flex h-20 items-center justify-center rounded-[10px] border border-[#fee2e2] bg-[#fff7f7] text-[14px] font-bold text-[#dc2626]">
            分类数据加载失败，请稍后重试。
          </div>
        ) : categoriesQuery.isLoading ? (
          <div className={`mt-3 flex gap-2 ${rhythm.homeThemeScroller}`}>
            {Array.from({ length: 8 }).map((_, index) => (
              <SkeletonBlock key={index} className="h-[52px] w-[176px] shrink-0" />
            ))}
          </div>
        ) : categories.length > 0 ? (
          <div className={`mt-3 flex snap-x gap-2 ${rhythm.homeThemeScroller}`}>
            {categories.map((row, index) => (
              <CategoryThemeCard key={String(row.id ?? row.category_code ?? index)} row={row} index={index} />
            ))}
          </div>
        ) : (
          <div className="mt-3 flex h-20 items-center justify-center rounded-[10px] border border-[#e7ecf5] bg-[#fbfcff] text-[14px] font-bold text-[#64748b]">
            暂无一级分类，导入馆藏数据后将在这里显示主题。
          </div>
        )}
      </section>
    </div>
  );
}
