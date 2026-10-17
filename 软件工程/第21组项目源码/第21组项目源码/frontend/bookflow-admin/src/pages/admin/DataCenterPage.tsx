import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { ErrorState } from "@/components/ui/ErrorState";
import { AITab, CollectionTab, HotColdTab, OverviewTab, ReadersTab } from "./DataCenterTabs";
import { buildDataCenterPDF } from "@/utils/export-pdf";
import rhythm from "@/styles/AdminRhythm.module.css";

type TabKey = "overview" | "collection" | "circulation" | "readers" | "ai";

function currentDateLabel() {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "overview", label: "运营总览" },
  { key: "collection", label: "馆藏健康" },
  { key: "circulation", label: "热门冷门" },
  { key: "readers", label: "读者分析" },
  { key: "ai", label: "AI 效率" },
];

function ExportPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div data-export-page data-export-title={title} className="bg-white pb-4">
      {children}
    </div>
  );
}

function waitForPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

export function DataCenterPage() {
  const [tab, setTab] = useState<TabKey>("overview");
  const [exporting, setExporting] = useState(false);
  const [exportWidth, setExportWidth] = useState(1120);

  const overview = useQuery({ queryKey: ["analytics", "overview"], queryFn: analyticsApi.overview });
  const collection = useQuery({ queryKey: ["analytics", "collection-health"], queryFn: analyticsApi.collectionHealth });
  const circulation = useQuery({ queryKey: ["analytics", "circulation"], queryFn: analyticsApi.circulation });
  const readerAnalytics = useQuery({ queryKey: ["analytics", "readers"], queryFn: analyticsApi.readers });
  const ai = useQuery({ queryKey: ["analytics", "ai-efficiency"], queryFn: analyticsApi.aiEfficiency });

  const handleExport = async () => {
    try {
      const visibleEl = document.getElementById("datacenter-content");
      setExportWidth(Math.max(980, Math.round(visibleEl?.getBoundingClientRect().width ?? 1120)));
      setExporting(true);
      await waitForPaint();
      const el = document.getElementById("datacenter-export-content");
      if (!el) throw new Error("Export container not found");
      await buildDataCenterPDF(el);
    } catch (err) {
      console.error("PDF export failed:", err);
      alert("导出失败：" + (err instanceof Error ? err.message : String(err)));
    } finally {
      setExporting(false);
    }
  };

  if ([overview, collection, circulation, readerAnalytics, ai].some((query) => query.isError)) {
    return <ErrorState onRetry={() => void Promise.all([overview.refetch(), collection.refetch(), circulation.refetch(), readerAnalytics.refetch(), ai.refetch()])} />;
  }

  const currentMetricDate = currentDateLabel();

  return (
    <div className={rhythm.page}>
      <div className="flex min-w-0 items-center justify-between gap-4 border-b border-[var(--bf-border-soft)]">
        <div className="flex min-w-0 gap-8">
          {tabs.map((item) => (
            <button key={item.key} type="button" onClick={() => setTab(item.key)} className={`relative h-12 whitespace-nowrap text-base font-black ${tab === item.key ? "text-[var(--bf-brand)]" : "text-[#1b2848]"}`}>
              {item.label}
              {tab === item.key ? <span className="absolute bottom-0 left-0 h-1 w-full rounded-full bg-[var(--bf-brand)]" /> : null}
            </button>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-3 pb-3">
          <button type="button" className="bf-control h-11 px-4 font-bold text-[#17213c]">{currentMetricDate}</button>
          <button type="button" className="bf-control h-11 px-4 font-bold text-[#17213c]" disabled={exporting} onClick={handleExport}>{exporting ? "导出中…" : "导出 PDF"}</button>
        </div>
      </div>

      <div id="datacenter-content" className="bg-white">
        {tab === "overview" && <OverviewTab data={overview.data ?? {}} loading={overview.isLoading} />}
        {tab === "collection" && <CollectionTab data={collection.data ?? {}} loading={collection.isLoading} />}
        {tab === "circulation" && <HotColdTab data={circulation.data ?? {}} collectionData={collection.data ?? {}} loading={circulation.isLoading} />}
        {tab === "readers" && <ReadersTab data={readerAnalytics.data ?? {}} circulationData={circulation.data ?? {}} collectionData={collection.data ?? {}} loading={readerAnalytics.isLoading} />}
        {tab === "ai" && <AITab data={ai.data ?? {}} loading={ai.isLoading} />}
      </div>
      {exporting ? (
        <div
          id="datacenter-export-content"
          aria-hidden="true"
          className="pointer-events-none fixed left-[-10000px] top-0 bg-white"
          style={{ width: exportWidth }}
        >
          <ExportPage title="overview">
            <OverviewTab data={overview.data ?? {}} loading={overview.isLoading} />
          </ExportPage>
          <ExportPage title="collection">
            <CollectionTab data={collection.data ?? {}} loading={collection.isLoading} />
          </ExportPage>
          <ExportPage title="hot-cold">
            <HotColdTab data={circulation.data ?? {}} collectionData={collection.data ?? {}} loading={circulation.isLoading} />
          </ExportPage>
          <ExportPage title="readers">
            <ReadersTab data={readerAnalytics.data ?? {}} circulationData={circulation.data ?? {}} collectionData={collection.data ?? {}} loading={readerAnalytics.isLoading} />
          </ExportPage>
          <ExportPage title="ai">
            <AITab data={ai.data ?? {}} loading={ai.isLoading} />
          </ExportPage>
        </div>
      ) : null}
    </div>
  );
}
