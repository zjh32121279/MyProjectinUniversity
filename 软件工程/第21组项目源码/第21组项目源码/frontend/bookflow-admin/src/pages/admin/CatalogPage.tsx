import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { analyticsApi } from "@/api/analytics";
import { catalogApi } from "@/api/catalog";
import { locationsApi } from "@/api/locations";
import { BookCover } from "@/components/ui/BookCover";
import { ActionButton } from "@/components/ui/ActionButton";
import { DataTable, DataTablePagination, type DataColumn } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterBar, FilterSelect } from "@/components/ui/FilterBar";
import { FormDialog } from "@/components/ui/FormDialog";
import { PageCard } from "@/components/ui/PageCard";
import { SearchInput } from "@/components/ui/SearchInput";
import { StatCard } from "@/components/ui/StatCard";
import { AppIcon, type AppIconName } from "@/components/icons/AppIcon";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { AnyRecord } from "@/types/api";
import { formatNumber } from "@/utils/format";
import { downloadCatalogCSV } from "@/utils/export";
import { formatCopyStatus } from "@/utils/labels";
import rhythm from "@/styles/AdminRhythm.module.css";
import { CategoryManagerDrawer } from "./CatalogCategoryManagerDrawer";

type CopyStatusFilter = "available" | "borrowed" | "reserved" | "unavailable";
type DrawerTab = "detail" | "copies";
type CopyDialogState = { type: "status" | "location" | "add"; copy?: AnyRecord } | null;

const COPY_STATUS_OPTIONS = [
  { value: "available", label: "在馆可借" },
  { value: "borrowed", label: "已借出" },
  { value: "reserved", label: "预约保留" },
  { value: "unavailable", label: "暂不可借" },
  { value: "maintenance", label: "维护中" },
];

const COVER_SPEC = {
  minWidth: 480,
  minHeight: 720,
  idealMinWidth: 600,
  idealMinHeight: 900,
  idealMaxWidth: 1200,
  idealMaxHeight: 1800,
  minRatio: 0.62,
  maxRatio: 0.78,
};
const MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024;
const COVER_UPLOAD_TYPES = new Set(["image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp"]);
const COVER_UPLOAD_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp"]);

type BookSubmitPayload = { body: AnyRecord; coverFile?: File | null };

function text(value: unknown, fallback = "-") {
  const result = String(value ?? "").trim();
  return result || fallback;
}

function num(value: unknown) {
  return Number(value ?? 0) || 0;
}

function copyStat(row: AnyRecord, status: CopyStatusFilter) {
  const stats = row.copy_stats && typeof row.copy_stats === "object" ? (row.copy_stats as AnyRecord) : {};
  return Number(stats[status] ?? 0);
}

function zoneLabel(row: AnyRecord) {
  const zone = row.primary_zone && typeof row.primary_zone === "object" ? (row.primary_zone as AnyRecord) : {};
  const code = text(zone.zone_code, "");
  const name = text(zone.zone_name, "");
  if (code && name) return `${code} · ${name}`;
  return code || name || "-";
}

function copyLocationLabel(copy: AnyRecord) {
  const loc = copy.location && typeof copy.location === "object" ? (copy.location as AnyRecord) : {};
  const zone = text(loc.zone_code, "");
  const zoneName = text(loc.zone_name, "");
  const shelf = text(loc.shelf_code, "");
  const position = text(loc.position_code ?? loc.shelf_position, "");
  const parts = [zoneName ? `${zone}${zone ? " · " : ""}${zoneName}` : zone, shelf, position].filter(Boolean);
  return parts.length ? parts.join(" / ") : "未分配架位";
}

function fieldClass() {
  return "h-10 w-full rounded-[12px] border border-[#dce4f2] bg-white px-3 text-sm font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)] focus:ring-4 focus:ring-blue-50";
}

function coverSpecText() {
  return `封面建议：竖版书封，宽高比 ${COVER_SPEC.minRatio}-${COVER_SPEC.maxRatio}，至少 ${COVER_SPEC.minWidth}×${COVER_SPEC.minHeight}px，推荐 ${COVER_SPEC.idealMinWidth}×${COVER_SPEC.idealMinHeight}-${COVER_SPEC.idealMaxWidth}×${COVER_SPEC.idealMaxHeight}px。`;
}

function readCoverSize(url: string) {
  return new Promise<{ width: number; height: number }>((resolve, reject) => {
    const image = new Image();
    const timer = window.setTimeout(() => {
      image.onload = null;
      image.onerror = null;
      reject(new Error("timeout"));
    }, 7000);
    image.onload = () => {
      window.clearTimeout(timer);
      resolve({ width: image.naturalWidth, height: image.naturalHeight });
    };
    image.onerror = () => {
      window.clearTimeout(timer);
      reject(new Error("load_failed"));
    };
    image.referrerPolicy = "no-referrer";
    image.src = url;
  });
}

function validateCoverSize(size: { width: number; height: number }) {
  const ratio = size.width / size.height;
  if (ratio < COVER_SPEC.minRatio || ratio > COVER_SPEC.maxRatio) {
    toast.error(`封面比例不合适：当前 ${size.width}×${size.height}，请使用竖版书封，宽高比保持在 ${COVER_SPEC.minRatio}-${COVER_SPEC.maxRatio}。`);
    return false;
  }
  if (size.width < COVER_SPEC.minWidth || size.height < COVER_SPEC.minHeight) {
    toast.error(`封面分辨率偏低：当前 ${size.width}×${size.height}，至少需要 ${COVER_SPEC.minWidth}×${COVER_SPEC.minHeight}px。`);
    return false;
  }
  if (size.width < COVER_SPEC.idealMinWidth || size.height < COVER_SPEC.idealMinHeight || size.width > COVER_SPEC.idealMaxWidth || size.height > COVER_SPEC.idealMaxHeight) {
    toast.warning(`封面可用，但建议控制在 ${COVER_SPEC.idealMinWidth}×${COVER_SPEC.idealMinHeight}-${COVER_SPEC.idealMaxWidth}×${COVER_SPEC.idealMaxHeight}px，当前 ${size.width}×${size.height}px。`);
  }
  return true;
}

async function validateCoverUrl(url: string) {
  const raw = url.trim();
  if (!raw) return true;
  if (/^www\./i.test(raw)) {
    toast.error("封面 URL 请以 https:// 或 http:// 开头。");
    return false;
  }

  let normalizedUrl = raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    if (!["http:", "https:", "data:", "blob:"].includes(parsed.protocol)) {
      toast.error("封面 URL 格式不正确。");
      return false;
    }
    normalizedUrl = parsed.href;
  } catch {
    toast.error("封面 URL 格式不正确。");
    return false;
  }

  let size: { width: number; height: number };
  try {
    size = await readCoverSize(normalizedUrl);
  } catch {
    toast.error("封面图片无法加载，请换一个可访问的图片链接。");
    return false;
  }

  return validateCoverSize(size);
}

async function validateCoverFile(file: File) {
  const suffix = file.name.includes(".") ? `.${file.name.split(".").pop()?.toLowerCase() ?? ""}` : "";
  if (!COVER_UPLOAD_TYPES.has(file.type) && !COVER_UPLOAD_EXTENSIONS.has(suffix)) {
    toast.error("封面文件仅支持 JPG、PNG 或 WebP 图片。");
    return false;
  }
  if (file.size > MAX_COVER_UPLOAD_BYTES) {
    toast.error("封面文件不能超过 5MB。");
    return false;
  }
  const previewUrl = URL.createObjectURL(file);
  try {
    return validateCoverSize(await readCoverSize(previewUrl));
  } catch {
    toast.error("封面图片无法读取，请换一张 JPG、PNG 或 WebP 图片。");
    return false;
  } finally {
    URL.revokeObjectURL(previewUrl);
  }
}

function CoverSpecHint() {
  return <p className="mt-1 text-[12px] font-semibold leading-5 text-[#64718d]">{coverSpecText()}</p>;
}

function CoverUploadField({
  title,
  code,
  categoryCode,
  currentCoverUrl,
  previewUrl,
  selectedFile,
  onFileChange,
}: {
  title?: string;
  code?: string;
  categoryCode?: string;
  currentCoverUrl?: string;
  previewUrl: string;
  selectedFile: File | null;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  const coverUrl = previewUrl || currentCoverUrl || "";
  return (
    <div className="rounded-[14px] border border-[#e8edf6] bg-[#fbfcff] p-3">
      <div className="flex items-start gap-3">
        <BookCover title={title} code={code} categoryCode={categoryCode} coverUrl={coverUrl} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-black text-[#31405f]">上传书封面</div>
          <p className="mt-1 text-[12px] font-semibold leading-5 text-[#64718d]">支持 JPG、PNG、WebP，文件不超过 5MB。</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-[10px] bg-[var(--bf-brand)] px-3 text-[12px] font-black text-white shadow-sm transition hover:bg-[var(--bf-brand-hover)]">
              <AppIcon name="image" size={15} />
              {selectedFile ? "更换图片" : "选择图片"}
              <input name="cover_file" type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={onFileChange} />
            </label>
            {selectedFile ? <span className="max-w-[260px] truncate text-[12px] font-bold text-[#31405f]">{selectedFile.name}</span> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-[14px] border border-[#edf1f7] bg-[#fbfcff] px-4 py-3">
      <div className="text-[12px] font-bold text-[var(--bf-text-secondary)]">{label}</div>
      <div className="mt-1 break-words text-[14px] font-bold leading-6 text-[#101a35]">{text(value)}</div>
    </div>
  );
}

function PositionSelect({ positions, value, onChange }: { positions: AnyRecord[]; value: string; onChange: (value: string) => void }) {
  return (
    <select className={fieldClass()} value={value} onChange={(event) => onChange(event.target.value)} required>
      <option value="">请选择馆藏位置</option>
      {positions.map((position) => {
        const id = String(position.id ?? "");
        const label = [position.zone_name, position.shelf_code, position.position_code].map((item) => text(item, "")).filter(Boolean).join(" / ");
        return <option key={id} value={id}>{label || id}</option>;
      })}
    </select>
  );
}

function CatalogIconButton({ label, icon, tone, onClick }: { label: string; icon: AppIconName; tone: "blue" | "purple" | "neutral"; onClick: () => void }) {
  const toneClass =
    tone === "purple"
      ? "border-[#ddd6fe] bg-[#f6f3ff] text-[#6d5dfc] hover:bg-[#ede9fe] focus:ring-purple-100"
      : tone === "neutral"
        ? "border-[#e2e8f0] bg-[#f8fafc] text-[#475569] hover:bg-[#f1f5f9] focus:ring-slate-100"
        : "border-[#bfdbfe] bg-[#eef5ff] text-[var(--bf-brand)] hover:bg-[#dbeafe] focus:ring-blue-100";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`group relative inline-flex h-8 w-8 items-center justify-center rounded-[10px] border transition focus:outline-none focus:ring-4 ${toneClass}`}
      onClick={onClick}
    >
      <AppIcon name={icon} size={16} />
      <span className="sr-only">{label}</span>
      <span className="pointer-events-none absolute left-1/2 bottom-full z-30 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded-[8px] bg-[#111827] px-2 py-1 text-[11px] font-bold text-white shadow-lg group-hover:block group-focus-visible:block">
        {label}
      </span>
    </button>
  );
}

export function CatalogPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [circulationType, setCirculationType] = useState("");
  const [categoryCode, setCategoryCode] = useState(() => searchParams.get("category_code") ?? "");
  const [subcategoryCode, setSubcategoryCode] = useState("");
  const [zoneCode, setZoneCode] = useState(() => searchParams.get("zone_code") ?? "");
  const [page, setPage] = useState(1);
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("detail");
  const [copyDialog, setCopyDialog] = useState<CopyDialogState>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [categoryManagerOpen, setCategoryManagerOpen] = useState(false);
  const pageSize = 5;

  const health = useQuery({ queryKey: ["analytics", "collection-health"], queryFn: analyticsApi.collectionHealth });
  const categoriesQuery = useQuery({ queryKey: ["catalog", "categories"], queryFn: () => catalogApi.categories({ limit: 200, offset: 0 }) });
  const subcategoriesQuery = useQuery({ queryKey: ["catalog", "subcategories", categoryCode], queryFn: () => catalogApi.subcategories({ category_code: categoryCode || undefined, limit: 500, offset: 0 }) });
  const zonesQuery = useQuery({ queryKey: ["locations", "zones", "catalog-filter"], queryFn: () => locationsApi.zones({ limit: 200, offset: 0 }) });
  const bookQuery = useQuery({
    queryKey: ["catalog", "books", keyword, circulationType, categoryCode, subcategoryCode, status, zoneCode, page, pageSize],
    queryFn: () => catalogApi.books({
      keyword: keyword || undefined,
      circulation_type: circulationType || undefined,
      category_code: categoryCode || undefined,
      subcategory_code: subcategoryCode || undefined,
      copy_status: status || undefined,
      zone_code: zoneCode || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
  });
  const detailQuery = useQuery({
    queryKey: ["catalog", "book-detail", selectedBookId],
    queryFn: () => catalogApi.bookDetail(Number(selectedBookId)),
    enabled: selectedBookId !== null,
  });
  const copyQuery = useQuery({
    queryKey: ["catalog", "book-copies", selectedBookId],
    queryFn: () => catalogApi.bookCopies(Number(selectedBookId), { limit: 120, offset: 0 }),
    enabled: selectedBookId !== null,
  });
  const positionsQuery = useQuery({ queryKey: ["locations", "positions", "catalog-management"], queryFn: () => locationsApi.positions({ limit: 200 }) });

  const invalidateCatalog = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["catalog"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics", "collection-health"] }),
    ]);
  };

  async function handleExport() {
    try {
      const result = await catalogApi.books({
        keyword: keyword || undefined,
        circulation_type: circulationType || undefined,
        category_code: categoryCode || undefined,
        subcategory_code: subcategoryCode || undefined,
        copy_status: status || undefined,
        zone_code: zoneCode || undefined,
        limit: 10000,
        offset: 0,
      });
      if ((result.items ?? []).length === 0) {
        alert("没有符合条件的数据可导出。");
        return;
      }
      downloadCatalogCSV(result.items ?? []);
    } catch (err) {
      const message = err instanceof Error ? err.message : "导出失败，请重试";
      alert(`导出失败：${message}`);
    }
  }

  const updateBookMutation = useMutation({
    mutationFn: async ({ bookId, body, coverFile }: { bookId: number } & BookSubmitPayload) => {
      const result = await catalogApi.updateBook(bookId, body);
      return coverFile ? catalogApi.uploadBookCover(bookId, coverFile) : result;
    },
    onSuccess: () => {
      setEditOpen(false);
      void invalidateCatalog();
    },
  });

  const createBookMutation = useMutation({
    mutationFn: async ({ body, coverFile }: BookSubmitPayload) => {
      const result = await catalogApi.createBook(body);
      const bookId = Number(result.id);
      return coverFile && bookId ? catalogApi.uploadBookCover(bookId, coverFile) : result;
    },
    onSuccess: () => {
      setCreateOpen(false);
      void invalidateCatalog();
    },
  });

  const addCopiesMutation = useMutation({
    mutationFn: ({ bookId, body }: { bookId: number; body: AnyRecord }) => catalogApi.createCopies(bookId, body),
    onSuccess: () => {
      setCopyDialog(null);
      void invalidateCatalog();
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ copyId, body }: { copyId: number; body: AnyRecord }) => catalogApi.updateCopyStatus(copyId, body),
    onSuccess: () => {
      setCopyDialog(null);
      void invalidateCatalog();
    },
  });

  const updateLocationMutation = useMutation({
    mutationFn: ({ copyId, body }: { copyId: number; body: AnyRecord }) => catalogApi.updateCopyLocation(copyId, body),
    onSuccess: () => {
      setCopyDialog(null);
      void invalidateCatalog();
    },
  });

  const rows = useMemo(() => bookQuery.data?.items ?? [], [bookQuery.data?.items]);
  const categories = categoriesQuery.data?.items ?? [];
  const subcategories = subcategoriesQuery.data?.items ?? [];
  const zones = zonesQuery.data?.items ?? [];

  const selectedBook = detailQuery.data ?? rows.find((item) => Number(item.id) === selectedBookId) ?? null;
  const copies = copyQuery.data?.items ?? [];
  const positions = positionsQuery.data?.items ?? [];

  function openBook(row: AnyRecord, tab: DrawerTab) {
    setSelectedBookId(Number(row.id));
    setDrawerTab(tab);
  }

  const columns: DataColumn<AnyRecord>[] = [
    {
      key: "title",
      title: "书名",
      width: "292px",
      render: (row) => (
        <div className="flex items-center gap-4 py-1.5">
          <BookCover title={String(row.title ?? "")} code={String(row.book_code ?? "")} categoryCode={String(row.category_code ?? "")} coverUrl={String(row.cover_url ?? "")} size="lg" />
          <div className="min-w-0">
            <div className="max-w-[202px] truncate text-[15px] font-bold leading-6 text-[#101a35]">{text(row.title)}</div>
            <div className="mt-1.5 max-w-[210px] truncate text-[12px] leading-5 text-[var(--bf-text-secondary)]">{text(row.author, "")} / {text(row.publisher, "")}</div>
          </div>
        </div>
      ),
    },
    { key: "book_code", title: "图书编号", width: "98px", nowrap: true, render: (row) => <span className="font-bold text-[var(--bf-brand)]">{text(row.book_code)}</span> },
    { key: "category", title: "一级分类", width: "86px", nowrap: true, render: (row) => <span className="block truncate">{text(row.category_name)}</span> },
    { key: "subcategory", title: "二级分类", width: "100px", nowrap: true, render: (row) => <span className="block truncate">{text(row.subcategory_name)}</span> },
    { key: "total", title: "实体", width: "52px", align: "center", render: (row) => formatNumber(row.total_copies) },
    { key: "available", title: "可借", width: "52px", align: "center", render: (row) => formatNumber(row.available_copies ?? copyStat(row, "available")) },
    { key: "borrowed", title: "已借", width: "52px", align: "center", render: (row) => formatNumber(row.borrowed_copies ?? copyStat(row, "borrowed")) },
    { key: "reserved", title: "保留", width: "52px", align: "center", render: (row) => formatNumber(row.reserved_copies ?? copyStat(row, "reserved")) },
    { key: "unavailable", title: "不可借", width: "62px", align: "center", nowrap: true, render: (row) => formatNumber(row.unavailable_copies ?? copyStat(row, "unavailable")) },
    { key: "zone", title: "主分区", width: "116px", nowrap: true, render: (row) => <span className="block truncate text-[var(--bf-text-secondary)]" title={zoneLabel(row)}>{zoneLabel(row)}</span> },
    { key: "status", title: "流通类型", width: "82px", align: "center", render: (row) => <StatusBadge value={row.circulation_type} tone={row.circulation_type === "热门" ? "red" : row.circulation_type === "冷门" ? "cyan" : "blue"} /> },
    {
      key: "visible_actions",
      title: "操作",
      width: "76px",
      align: "center",
      nowrap: true,
      render: (row) => (
        <div className="flex items-center justify-center gap-2">
          <CatalogIconButton label="查看详情" icon="eye" tone="blue" onClick={() => openBook(row, "detail")} />
          <CatalogIconButton label="副本管理" icon="queue" tone="purple" onClick={() => openBook(row, "copies")} />
        </div>
      ),
    },
  ];

  if (health.isError || bookQuery.isError) return <ErrorState onRetry={() => void Promise.all([health.refetch(), bookQuery.refetch()])} />;

  const hasTableContent = health.isLoading || bookQuery.isLoading || rows.length > 0;
  const collection = health.data ?? {};
  const statCards = [
    { title: "图书种数", value: formatNumber(collection.total_books), unit: "种", icon: "catalog", tone: "blue" as const },
    { title: "实体册数", value: formatNumber(collection.total_copies), unit: "册", icon: "data", tone: "green" as const },
    { title: "可外借册数", value: formatNumber(collection.available_copies), unit: "册", icon: "readers", tone: "purple" as const },
    { title: "暂不可借", value: formatNumber(collection.unavailable_copies), unit: "册", icon: "overdue", tone: "orange" as const },
    { title: "待上架", value: formatNumber(collection.pending_shelving_count), unit: "册", icon: "queue", tone: "cyan" as const },
  ];

  return (
    <div className={rhythm.page}>
      <div className="grid grid-cols-5 gap-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} compact />
        ))}
      </div>

      <PageCard className={`${rhythm.pagedCard} ${hasTableContent ? rhythm.catalogCard : rhythm.emptyTableCard}`} bodyClassName={rhythm.pagedBody}>
        <FilterBar className="flex-nowrap gap-3 px-5 py-4">
          <FilterSelect className="w-[128px] min-w-[128px]" value={categoryCode} onChange={(event) => { setCategoryCode(event.target.value); setSubcategoryCode(""); setPage(1); }}>
            <option value="">一级分类：全部</option>
            {categories.map((item) => <option key={String(item.category_code)} value={String(item.category_code)}>{text(item.category_name)}</option>)}
          </FilterSelect>
          <FilterSelect className="w-[128px] min-w-[128px]" value={subcategoryCode} onChange={(event) => { setSubcategoryCode(event.target.value); setPage(1); }}>
            <option value="">二级分类：全部</option>
            {subcategories.map((item) => <option key={String(item.subcategory_code)} value={String(item.subcategory_code)}>{text(item.subcategory_name)}</option>)}
          </FilterSelect>
          <FilterSelect className="w-[128px] min-w-[128px]" value={circulationType} onChange={(event) => { setCirculationType(event.target.value); setPage(1); }}>
            <option value="">流通类型：全部</option>
            <option value="热门">热门图书</option>
            <option value="普通">普通图书</option>
            <option value="冷门">冷门图书</option>
          </FilterSelect>
          <FilterSelect className="w-[128px] min-w-[128px]" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
            <option value="">馆藏状态：全部</option>
            <option value="available">{formatCopyStatus("available")}</option>
            <option value="borrowed">{formatCopyStatus("borrowed")}</option>
            <option value="reserved">{formatCopyStatus("reserved")}</option>
            <option value="unavailable">{formatCopyStatus("unavailable")}</option>
          </FilterSelect>
          <FilterSelect className="w-[128px] min-w-[128px]" value={zoneCode} onChange={(event) => { setZoneCode(event.target.value); setPage(1); }}>
            <option value="">主要分区：全部</option>
            {zones.map((item) => <option key={String(item.zone_code)} value={String(item.zone_code)}>{text(item.zone_name)}</option>)}
          </FilterSelect>
          <SearchInput className="ml-auto w-[280px] shrink-0" value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1); }} placeholder="搜索书名、作者、图书编号" />
          <CatalogIconButton label="管理分类" icon="catalog" tone="purple" onClick={() => setCategoryManagerOpen(true)} />
          <CatalogIconButton label="导出数据" icon="export" tone="neutral" onClick={handleExport} />
          <CatalogIconButton label="新增书籍" icon="plus" tone="blue" onClick={() => setCreateOpen(true)} />
        </FilterBar>
        {hasTableContent ? (
          <DataTable
            className={`${rhythm.pagedTable} ${rhythm.catalogTable} [&_table]:min-w-[1120px]`}
            columns={columns}
            rows={rows}
            loading={bookQuery.isLoading || health.isLoading}
            emptyTitle="暂无馆藏记录"
            emptyMode="none"
            footer={
              <DataTablePagination
                total={bookQuery.data?.total ?? 0}
                page={page}
                pageSize={pageSize}
                onPageChange={setPage}
              />
            }
          />
        ) : null}
      </PageCard>

      <FormDialog open={selectedBookId !== null} onOpenChange={(open) => { if (!open) setSelectedBookId(null); }} title="馆藏详情">
        <div className="flex gap-2 rounded-[16px] bg-[#f4f7fb] p-1">
          {[
            ["detail", "图书详情"],
            ["copies", "副本管理"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`h-10 flex-1 rounded-[12px] text-sm font-black transition ${drawerTab === key ? "bg-white text-[var(--bf-brand)] shadow-sm" : "text-[var(--bf-text-secondary)]"}`}
              onClick={() => setDrawerTab(key as DrawerTab)}
            >
              {label}
            </button>
          ))}
        </div>

        {detailQuery.isLoading ? <div className="mt-5 rounded-[16px] bg-[#f8fafc] p-5 text-sm font-bold text-[var(--bf-text-secondary)]">正在加载馆藏详情...</div> : null}

        {selectedBook && drawerTab === "detail" ? (
          <div className="mt-5 space-y-5">
            <div className="flex items-center gap-4 rounded-[18px] border border-[#e7edf6] bg-white p-4">
              <BookCover title={text(selectedBook.title)} code={text(selectedBook.book_code)} categoryCode={text(selectedBook.category_code, "")} coverUrl={text(selectedBook.cover_url, "")} size="lg" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[18px] font-black text-[#101a35]">{text(selectedBook.title)}</div>
                <div className="mt-1 truncate text-sm font-semibold text-[var(--bf-text-secondary)]">{text(selectedBook.author, "未知作者")} / {text(selectedBook.publisher, "未知出版社")}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <StatusBadge value={selectedBook.circulation_type} tone={selectedBook.circulation_type === "热门" ? "red" : selectedBook.circulation_type === "冷门" ? "cyan" : "blue"} />
                  <StatusBadge value={selectedBook.status === "active" ? "正常在库" : "停用"} tone={selectedBook.status === "active" ? "green" : "gray"} />
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <DetailItem label="图书编号" value={selectedBook.book_code} />
              <DetailItem label="ISBN" value={selectedBook.isbn} />
              <DetailItem label="一级分类" value={selectedBook.category_name} />
              <DetailItem label="二级分类" value={selectedBook.subcategory_name} />
              <DetailItem label="出版年份" value={selectedBook.publish_year} />
              <DetailItem label="语言 / 版次" value={`${text(selectedBook.language)} / ${text(selectedBook.edition)}`} />
              <DetailItem label="页数 / 价格" value={`${text(selectedBook.pages)} / ${text(selectedBook.price_yuan)}`} />
              <DetailItem label="CLC / 索书号" value={`${text(selectedBook.clc_code)} / ${text(selectedBook.call_number)}`} />
              <DetailItem label="ISBN 状态" value={selectedBook.isbn_status} />
              <DetailItem label="编目状态" value={selectedBook.bibliographic_status} />
              <DetailItem label="书目来源" value={selectedBook.book_source_class} />
              <DetailItem label="主分区" value={zoneLabel(selectedBook)} />
              <DetailItem label="可借 / 总册数" value={`${formatNumber(selectedBook.available_copies)} / ${formatNumber(selectedBook.total_copies)}`} />
            </div>
            <div className="rounded-[18px] border border-[#edf1f7] bg-[#fbfcff] p-4">
              <div className="text-sm font-black text-[#101a35]">简介与关键词</div>
              <p className="mt-3 text-sm font-semibold leading-7 text-[var(--bf-text-secondary)]">{text(selectedBook.introduction, "暂无简介")}</p>
              <div className="mt-3 text-xs font-bold text-[var(--bf-text-secondary)]">关键词：{text(selectedBook.keywords, "暂无")}</div>
            </div>
            <div className="flex gap-3">
              <ActionButton icon="edit" onClick={() => setEditOpen(true)}>编辑图书详情</ActionButton>
              <ActionButton variant="secondary" icon="queue" onClick={() => setDrawerTab("copies")}>管理副本</ActionButton>
            </div>
          </div>
        ) : null}

        {selectedBook && drawerTab === "copies" ? (
          <div className="mt-5 space-y-4">
            <div className="flex items-center justify-between rounded-[18px] border border-[#e7edf6] bg-[#fbfcff] px-4 py-3">
              <div>
                <div className="text-sm font-black text-[#101a35]">{text(selectedBook.title)}</div>
                <div className="mt-1 text-xs font-bold text-[var(--bf-text-secondary)]">副本、馆藏位置和状态流转统一在这里处理</div>
              </div>
              <ActionButton size="sm" icon="plus" onClick={() => setCopyDialog({ type: "add" })}>新增副本</ActionButton>
            </div>
            {copyQuery.isLoading ? <div className="rounded-[16px] bg-[#f8fafc] p-5 text-sm font-bold text-[var(--bf-text-secondary)]">正在加载副本...</div> : null}
            <div className="space-y-3">
              {copies.map((copy) => (
                <div key={String(copy.id)} className="rounded-[18px] border border-[#e8edf6] bg-white p-4 shadow-[0_10px_26px_rgba(15,23,42,0.04)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-black text-[#101a35]">{text(copy.copy_code)}</span>
                        <StatusBadge value={copy.copy_status} />
                      </div>
                      <div className="mt-2 text-xs font-bold text-[var(--bf-text-secondary)]">条码：{text(copy.barcode)}</div>
                      <div className="mt-1 text-xs font-bold text-[var(--bf-text-secondary)]">馆藏位置：{copyLocationLabel(copy)}</div>
                      {copy.current_borrow_summary ? <div className="mt-1 text-xs font-bold text-[#dc2626]">当前借出中，状态限制由后端规则校验</div> : null}
                    </div>
                    <div className="flex shrink-0 flex-col gap-2">
                      <ActionButton size="sm" variant="secondary" icon="refresh" onClick={() => setCopyDialog({ type: "status", copy })}>状态流转</ActionButton>
                      <ActionButton size="sm" variant="secondary" icon="catalog" onClick={() => setCopyDialog({ type: "location", copy })}>调整位置</ActionButton>
                    </div>
                  </div>
                </div>
              ))}
              {!copyQuery.isLoading && !copies.length ? <div className="rounded-[18px] border border-dashed border-[#dce4f2] bg-[#fbfcff] p-6 text-center text-sm font-bold text-[var(--bf-text-secondary)]">暂无副本，可以新增副本后分配架位。</div> : null}
            </div>
          </div>
        ) : null}
      </FormDialog>

      <BookEditDialog
        open={editOpen}
        book={selectedBook}
        pending={updateBookMutation.isPending}
        onOpenChange={setEditOpen}
        onSubmit={(body, coverFile) => selectedBookId !== null && updateBookMutation.mutate({ bookId: selectedBookId, body, coverFile })}
      />
      <BookCreateDialog
        open={createOpen}
        categories={categories}
        subcategories={subcategories}
        zones={zones}
        pending={createBookMutation.isPending}
        onOpenChange={setCreateOpen}
        onSubmit={(body, coverFile) => createBookMutation.mutate({ body, coverFile })}
      />
      <CopyActionDialog
        state={copyDialog}
        bookId={selectedBookId}
        positions={positions}
        pending={addCopiesMutation.isPending || updateStatusMutation.isPending || updateLocationMutation.isPending}
        onOpenChange={(open) => { if (!open) setCopyDialog(null); }}
        onSubmitAdd={(body) => selectedBookId !== null && addCopiesMutation.mutate({ bookId: selectedBookId, body })}
        onSubmitStatus={(copyId, body) => updateStatusMutation.mutate({ copyId, body })}
        onSubmitLocation={(copyId, body) => updateLocationMutation.mutate({ copyId, body })}
      />

      <CategoryManagerDrawer open={categoryManagerOpen} onOpenChange={setCategoryManagerOpen} />
    </div>
  );
}

function BookCreateDialog({ open, categories, subcategories, zones, pending, onOpenChange, onSubmit }: { open: boolean; categories: AnyRecord[]; subcategories: AnyRecord[]; zones: AnyRecord[]; pending: boolean; onOpenChange: (open: boolean) => void; onSubmit: (body: AnyRecord, coverFile?: File | null) => void }) {
  const [checkingCover, setCheckingCover] = useState(false);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreviewUrl, setCoverPreviewUrl] = useState("");

  useEffect(() => {
    if (!open) {
      setCheckingCover(false);
      setCoverFile(null);
      setCoverPreviewUrl("");
    }
  }, [open]);

  useEffect(() => () => {
    if (coverPreviewUrl) URL.revokeObjectURL(coverPreviewUrl);
  }, [coverPreviewUrl]);

  function handleCoverFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setCoverFile(file);
    setCoverPreviewUrl(file ? URL.createObjectURL(file) : "");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const categoryCodeValue = text(form.get("category_code"), "");
    const matchedCategory = categories.find((item) => String(item.category_code) === categoryCodeValue);
    const subcategoryCodeValue = text(form.get("subcategory_code"), "");
    const matchedSubcategory = subcategories.find((item) => String(item.subcategory_code) === subcategoryCodeValue);
    const zoneCodeValue = text(form.get("primary_zone_code"), "");
    const matchedZone = zones.find((item) => String(item.zone_code) === zoneCodeValue);
    const coverUrl = text(form.get("cover_url"), "");
    setCheckingCover(true);
    const coverValid = coverFile ? await validateCoverFile(coverFile) : await validateCoverUrl(coverUrl);
    setCheckingCover(false);
    if (!coverValid) return;
    onSubmit({
      title: text(form.get("title")),
      author: text(form.get("author"), ""),
      publisher: text(form.get("publisher"), ""),
      publish_year: Number(form.get("publish_year")) || null,
      isbn: text(form.get("isbn"), ""),
      category_id: matchedCategory ? Number(matchedCategory.id) : null,
      category_code: categoryCodeValue || null,
      subcategory_id: matchedSubcategory ? Number(matchedSubcategory.id) : null,
      subcategory_code: subcategoryCodeValue || null,
      primary_zone_id: matchedZone ? Number(matchedZone.id) : null,
      primary_zone_code: zoneCodeValue || null,
      cover_url: coverFile ? null : coverUrl || null,
      cover_source: coverFile ? null : coverUrl ? "manual" : null,
      cover_status: coverFile ? "missing" : coverUrl ? "ready" : "missing",
    }, coverFile);
  }
  return (
    <FormDialog open={open} onOpenChange={onOpenChange} title="新增书籍">
      <form className="space-y-3" onSubmit={handleSubmit}>
        <p className="text-[13px] font-semibold text-[#64718d]">书名和一级分类必填，其余可后续在详情中补充</p>
        <input name="title" className={fieldClass()} placeholder="书名 *" required />
        <div className="grid grid-cols-2 gap-3">
          <input name="author" className={fieldClass()} placeholder="作者" />
          <input name="publisher" className={fieldClass()} placeholder="出版社" />
          <input name="publish_year" className={fieldClass()} placeholder="出版年份" inputMode="numeric" />
          <input name="isbn" className={fieldClass()} placeholder="ISBN" />
        </div>
        <CoverUploadField previewUrl={coverPreviewUrl} selectedFile={coverFile} onFileChange={handleCoverFileChange} />
        <div>
          <input name="cover_url" className={fieldClass()} placeholder="封面 URL（可选）" />
          <CoverSpecHint />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <select name="category_code" className={fieldClass()} defaultValue="" required>
            <option value="">一级分类 *</option>
            {categories.map((item) => <option key={String(item.category_code)} value={String(item.category_code)}>{text(item.category_name)}</option>)}
          </select>
          <select name="subcategory_code" className={fieldClass()} defaultValue="">
            <option value="">二级分类</option>
            {subcategories.map((item) => <option key={String(item.subcategory_code)} value={String(item.subcategory_code)}>{text(item.subcategory_name)}</option>)}
          </select>
          <select name="primary_zone_code" className={fieldClass()} defaultValue="">
            <option value="">主分区</option>
            {zones.map((item) => <option key={String(item.zone_code)} value={String(item.zone_code)}>{text(item.zone_name)}</option>)}
          </select>
        </div>
        <div className="mt-4 flex justify-end gap-3">
          <ActionButton type="button" variant="ghost" onClick={() => onOpenChange(false)}>取消</ActionButton>
          <ActionButton type="submit" variant="primary" disabled={pending || checkingCover}>{checkingCover ? "检查封面" : pending ? "新增中" : "新增书籍"}</ActionButton>
        </div>
      </form>
    </FormDialog>
  );
}

function BookEditDialog({ open, book, pending, onOpenChange, onSubmit }: { open: boolean; book: AnyRecord | null; pending: boolean; onOpenChange: (open: boolean) => void; onSubmit: (body: AnyRecord, coverFile?: File | null) => void }) {
  const [checkingCover, setCheckingCover] = useState(false);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreviewUrl, setCoverPreviewUrl] = useState("");

  useEffect(() => {
    setCheckingCover(false);
    setCoverFile(null);
    setCoverPreviewUrl("");
  }, [open, book?.id]);

  useEffect(() => () => {
    if (coverPreviewUrl) URL.revokeObjectURL(coverPreviewUrl);
  }, [coverPreviewUrl]);

  function handleCoverFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setCoverFile(file);
    setCoverPreviewUrl(file ? URL.createObjectURL(file) : "");
  }

  if (!book) return null;
  const currentBook = book;
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const coverUrl = text(form.get("cover_url"), "");
    setCheckingCover(true);
    const coverValid = coverFile ? await validateCoverFile(coverFile) : await validateCoverUrl(coverUrl);
    setCheckingCover(false);
    if (!coverValid) return;
    onSubmit({
      title: text(form.get("title")),
      author: text(form.get("author"), ""),
      publisher: text(form.get("publisher"), ""),
      publish_year: Number(form.get("publish_year")) || null,
      isbn: text(form.get("isbn"), ""),
      language: text(form.get("language"), ""),
      edition: text(form.get("edition"), ""),
      pages: Number(form.get("pages")) || null,
      price_yuan: Number(form.get("price_yuan")) || null,
      clc_code: text(form.get("clc_code"), ""),
      call_number: text(form.get("call_number"), ""),
      isbn_status: text(form.get("isbn_status"), ""),
      bibliographic_status: text(form.get("bibliographic_status"), ""),
      book_source_class: text(form.get("book_source_class"), ""),
      cover_url: coverFile ? text(currentBook.cover_url, "") : coverUrl,
      recommended_reader: text(form.get("recommended_reader"), ""),
      data_note: text(form.get("data_note"), ""),
      keywords: text(form.get("keywords"), ""),
      introduction: text(form.get("introduction"), ""),
      circulation_type: text(form.get("circulation_type"), "普通"),
      is_active: form.get("is_active") === "active",
    }, coverFile);
  }
  return (
    <FormDialog open={open} onOpenChange={onOpenChange} title="编辑图书详情">
      <form className="space-y-3" onSubmit={handleSubmit}>
        <input name="title" className={fieldClass()} defaultValue={text(book.title, "")} placeholder="书名" required />
        <div className="grid grid-cols-2 gap-3">
          <input name="author" className={fieldClass()} defaultValue={text(book.author, "")} placeholder="作者" />
          <input name="publisher" className={fieldClass()} defaultValue={text(book.publisher, "")} placeholder="出版社" />
          <input name="publish_year" className={fieldClass()} defaultValue={text(book.publish_year, "")} placeholder="出版年份" inputMode="numeric" />
          <input name="isbn" className={fieldClass()} defaultValue={text(book.isbn, "")} placeholder="ISBN" />
        </div>
        <CoverUploadField
          title={text(book.title, "")}
          code={text(book.book_code, "")}
          categoryCode={text(book.category_code, "")}
          currentCoverUrl={text(book.cover_url, "")}
          previewUrl={coverPreviewUrl}
          selectedFile={coverFile}
          onFileChange={handleCoverFileChange}
        />
        <div>
          <input name="cover_url" className={fieldClass()} defaultValue={text(book.cover_url, "")} placeholder="封面 URL（留空则使用分类占位封面）" />
          <CoverSpecHint />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input name="language" className={fieldClass()} defaultValue={text(book.language, "")} placeholder="语言" />
          <input name="edition" className={fieldClass()} defaultValue={text(book.edition, "")} placeholder="版次" />
          <input name="pages" className={fieldClass()} defaultValue={text(book.pages, "")} placeholder="页数" inputMode="numeric" />
          <input name="price_yuan" className={fieldClass()} defaultValue={text(book.price_yuan, "")} placeholder="价格" inputMode="decimal" />
          <input name="clc_code" className={fieldClass()} defaultValue={text(book.clc_code, "")} placeholder="CLC 分类号" />
          <input name="call_number" className={fieldClass()} defaultValue={text(book.call_number, "")} placeholder="索书号" />
          <input name="isbn_status" className={fieldClass()} defaultValue={text(book.isbn_status, "")} placeholder="ISBN 状态" />
          <input name="bibliographic_status" className={fieldClass()} defaultValue={text(book.bibliographic_status, "")} placeholder="编目状态" />
          <input name="book_source_class" className={fieldClass()} defaultValue={text(book.book_source_class, "")} placeholder="书目来源" />
          <input name="recommended_reader" className={fieldClass()} defaultValue={text(book.recommended_reader, "")} placeholder="推荐读者" />
        </div>
        <input name="keywords" className={fieldClass()} defaultValue={text(book.keywords, "")} placeholder="关键词" />
        <input name="data_note" className={fieldClass()} defaultValue={text(book.data_note, "")} placeholder="数据备注" />
        <textarea name="introduction" className="min-h-[96px] w-full rounded-[12px] border border-[#dce4f2] bg-white px-3 py-3 text-sm font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)] focus:ring-4 focus:ring-blue-50" defaultValue={text(book.introduction, "")} placeholder="简介" />
        <div className="grid grid-cols-2 gap-3">
          <select name="circulation_type" className={fieldClass()} defaultValue={text(book.circulation_type, "普通")}>
            <option value="热门">热门</option>
            <option value="普通">普通</option>
            <option value="冷门">冷门</option>
          </select>
          <select name="is_active" className={fieldClass()} defaultValue={book.status === "active" ? "active" : "inactive"}>
            <option value="active">正常在库</option>
            <option value="inactive">停用</option>
          </select>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <ActionButton variant="secondary" onClick={() => onOpenChange(false)}>取消</ActionButton>
          <ActionButton type="submit" icon="check" disabled={pending || checkingCover}>{checkingCover ? "检查封面" : pending ? "保存中" : "保存"}</ActionButton>
        </div>
      </form>
    </FormDialog>
  );
}

function CopyActionDialog({
  state,
  bookId,
  positions,
  pending,
  onOpenChange,
  onSubmitAdd,
  onSubmitStatus,
  onSubmitLocation,
}: {
  state: CopyDialogState;
  bookId: number | null;
  positions: AnyRecord[];
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitAdd: (body: AnyRecord) => void;
  onSubmitStatus: (copyId: number, body: AnyRecord) => void;
  onSubmitLocation: (copyId: number, body: AnyRecord) => void;
}) {
  const [positionId, setPositionId] = useState("");
  if (!state || bookId === null) return null;
  const copyId = Number(state.copy?.id ?? 0);

  function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmitAdd({
      count: Number(form.get("count")) || 1,
      copy_code: text(form.get("copy_code"), "") || null,
      barcode: text(form.get("barcode"), "") || null,
      current_position_id: Number(form.get("position_id")) || null,
      copy_status: text(form.get("copy_status"), "available"),
      collection_type: text(form.get("collection_type"), "普通外借"),
      acquisition_source: text(form.get("acquisition_source"), ""),
      condition_level: text(form.get("condition_level"), ""),
      asset_price_yuan: Number(form.get("asset_price_yuan")) || null,
      can_borrow_outside_library: form.get("can_borrow_outside_library") === "on",
      remark: text(form.get("remark"), ""),
    });
  }

  function handleStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmitStatus(copyId, { new_status: text(form.get("new_status"), "available"), reason: text(form.get("reason"), "人工调整副本状态") });
  }

  function handleLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onSubmitLocation(copyId, { current_position_id: Number(form.get("position_id")), reason: text(form.get("reason"), "人工调整馆藏位置") });
  }

  if (state.type === "add") {
    return (
      <FormDialog open onOpenChange={onOpenChange} title="新增馆藏副本">
        <form className="space-y-3" onSubmit={handleAdd}>
          <div className="grid grid-cols-2 gap-3">
            <input name="count" className={fieldClass()} defaultValue="1" min="1" max="100" type="number" />
            <select name="copy_status" className={fieldClass()} defaultValue="available">
              {COPY_STATUS_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input name="copy_code" className={fieldClass()} placeholder="副本编号（单册可填）" />
            <input name="barcode" className={fieldClass()} placeholder="条码号（单册可填）" />
          </div>
          <PositionSelect positions={positions} value={positionId} onChange={setPositionId} />
          <input name="position_id" type="hidden" value={positionId} />
          <div className="grid grid-cols-2 gap-3">
            <input name="collection_type" className={fieldClass()} defaultValue="普通外借" placeholder="馆藏类型" />
            <input name="condition_level" className={fieldClass()} placeholder="品相等级" />
            <input name="acquisition_source" className={fieldClass()} placeholder="采购/入藏来源" />
            <input name="asset_price_yuan" className={fieldClass()} placeholder="资产价格" inputMode="decimal" />
          </div>
          <label className="flex items-center gap-2 rounded-[12px] bg-[#f8fafc] px-3 py-2 text-sm font-bold text-[#172033]"><input name="can_borrow_outside_library" type="checkbox" defaultChecked /> 可外借</label>
          <input name="remark" className={fieldClass()} placeholder="备注，暂不可借/维护中建议填写原因" />
          <div className="flex justify-end gap-3 pt-2">
            <ActionButton variant="secondary" onClick={() => onOpenChange(false)}>取消</ActionButton>
            <ActionButton type="submit" icon="plus" disabled={pending}>{pending ? "新增中" : "新增副本"}</ActionButton>
          </div>
        </form>
      </FormDialog>
    );
  }

  if (state.type === "status") {
    return (
      <FormDialog open onOpenChange={onOpenChange} title="副本状态流转">
        <form className="space-y-3" onSubmit={handleStatus}>
          <div className="rounded-[14px] bg-[#f8fafc] px-4 py-3 text-sm font-bold text-[#101a35]">{text(state.copy?.copy_code)} 当前状态：{formatCopyStatus(state.copy?.copy_status)}</div>
          <select name="new_status" className={fieldClass()} defaultValue={text(state.copy?.copy_status, "available")}>
            {COPY_STATUS_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <input name="reason" className={fieldClass()} defaultValue="人工调整副本状态" placeholder="流转原因" />
          <div className="flex justify-end gap-3 pt-2">
            <ActionButton variant="secondary" onClick={() => onOpenChange(false)}>取消</ActionButton>
            <ActionButton type="submit" icon="refresh" disabled={pending}>{pending ? "更新中" : "更新状态"}</ActionButton>
          </div>
        </form>
      </FormDialog>
    );
  }

  return (
    <FormDialog open onOpenChange={onOpenChange} title="调整馆藏位置">
      <form className="space-y-3" onSubmit={handleLocation}>
        <div className="rounded-[14px] bg-[#f8fafc] px-4 py-3 text-sm font-bold text-[#101a35]">{text(state.copy?.copy_code)} 当前：{copyLocationLabel(state.copy ?? {})}</div>
        <PositionSelect positions={positions} value={positionId} onChange={setPositionId} />
        <input name="position_id" type="hidden" value={positionId} />
        <input name="reason" className={fieldClass()} defaultValue="人工调整馆藏位置" placeholder="位置变更原因" />
        <div className="flex justify-end gap-3 pt-2">
          <ActionButton variant="secondary" onClick={() => onOpenChange(false)}>取消</ActionButton>
          <ActionButton type="submit" icon="check" disabled={pending || !positionId}>{pending ? "保存中" : "保存位置"}</ActionButton>
        </div>
      </form>
    </FormDialog>
  );
}
