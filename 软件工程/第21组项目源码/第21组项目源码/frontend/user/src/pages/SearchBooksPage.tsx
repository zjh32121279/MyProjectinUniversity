import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Filter, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import { BookListItem } from "@/components/books/BookListItem";
import { LibraryMapCard } from "@/components/books/LibraryMapCard";
import { ReaderBookDetailDialog } from "@/components/books/ReaderBookDetail";
import { EmptyState } from "@/components/common/EmptyState";
import { FlowFeedback } from "@/components/common/FlowFeedback";
import { GlassCard } from "@/components/common/GlassCard";
import { Pagination } from "@/components/common/Pagination";
import { useBookCopies, useBookDetail, useBookFilters, useBookSearch } from "@/hooks/useBookSearch";
import { bookApi } from "@/services/bookApi";
import { borrowApi } from "@/services/borrowApi";
import { getReaderSession } from "@/services/readerApi";
import { reservationApi } from "@/services/reservationApi";
import type { BookCopy, BookItem } from "@/types/book";

const LIMIT = 4;

function cleanReaderText(value?: string | null) {
  return (value || "").replace(/小型公共图书馆/g, "公共图书馆").replace(/小型公共/g, "公共").replace(/小型/g, "").trim();
}

function copyLabel(value: string) {
  const map: Record<string, string> = {
    available: "可借",
    unavailable: "暂不可借",
    none: "暂不可借",
    borrowed: "已借出",
    reserved: "预约保留",
    maintenance: "维护中",
  };
  return map[value] || value || "全部";
}

function setOrDelete(next: URLSearchParams, key: string, value: string) {
  if (value) next.set(key, value);
  else next.delete(key);
}

function numberParam(value: string | null) {
  const next = Number(value);
  return Number.isFinite(next) && next > 0 ? next : null;
}

export function SearchBooksPage() {
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState(params.get("query") || "");
  const [offset, setOffset] = useState(Number(params.get("offset") || 0));
  const [selected, setSelected] = useState<BookItem | null>(null);
  const [detailBook, setDetailBook] = useState<BookItem | null>(null);
  const [selectedCopyId, setSelectedCopyId] = useState<number | null>(null);
  const query = params.get("query") || "";
  const category = params.get("category") || "";
  const availability = params.get("availability") || "";
  const zone = params.get("zone") || "";
  const floor = params.get("floor") || "";
  const targetFloor = params.get("target_floor") || "";
  const targetBookId = numberParam(params.get("book_id"));
  const targetCopyId = numberParam(params.get("copy_id"));
  const sort = params.get("sort") || "availability";

  const books = useBookSearch({ keyword: query || undefined, category_code: category || undefined, availability: availability || undefined, zone: zone || undefined, floor: floor || undefined, sort: sort || undefined, limit: LIMIT, offset });
  const targetBook = useBookDetail(targetBookId);
  const filters = useBookFilters();
  const queryClient = useQueryClient();
  const session = getReaderSession();
  const [message, setMessage] = useState("");
  const items = books.data?.items ?? [];
  const filterData = filters.data;
  const categories = filterData?.categories ?? [];
  const zones = filterData?.zones ?? [];
  const floors = filterData?.floors ?? [];
  const selectedBook = useMemo(() => selected || null, [selected]);
  const copies = useBookCopies(selectedBook?.id);
  const copyItems = useMemo(() => copies.data?.items ?? selectedBook?.sample_copies ?? [], [copies.data?.items, selectedBook?.sample_copies]);
  const selectedCopy = useMemo(
    () => copyItems.find((copy) => copy.id === selectedCopyId) ?? null,
    [copyItems, selectedCopyId],
  );
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setInput(query);
  }, [query]);

  useEffect(() => {
    setSelected(null);
    setSelectedCopyId(null);
  }, [query, category, availability, zone, floor, sort, offset]);

  useEffect(() => {
    if (targetBookId && selectedBook?.id === targetBookId) return;
    setSelectedCopyId(null);
  }, [selectedBook?.id, targetBookId]);

  useEffect(() => {
    if (!targetBookId) return;
    const book = targetBook.data ?? items.find((item) => item.id === targetBookId) ?? null;
    if (!book) return;

    setSelected((current) => (current?.id === book.id ? current : book));
    if (targetCopyId) setSelectedCopyId(targetCopyId);
    setMessage("已定位到推荐图书，请查看右侧馆藏地图。");
    setTimeout(() => mapRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
  }, [items, targetBook.data, targetBookId, targetCopyId]);

  const reserveMutation = useMutation({
    mutationFn: (book: BookItem) => reservationApi.createReservation({ book_id: book.id }),
    onSuccess: async () => {
      setMessage("预约已提交，可在“我的预约”中查看处理进度。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["reservation-list"] }),
        queryClient.invalidateQueries({ queryKey: ["reservation-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["book-search"] }),
        queryClient.invalidateQueries({ queryKey: ["book-copies"] }),
      ]);
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : "预约服务暂不可用");
    },
  });

  const borrowMutation = useMutation({
    mutationFn: ({ bookId, copyId }: { bookId: number; copyId: number }) => borrowApi.requestBorrow({ book_id: bookId, copy_id: copyId }),
    onSuccess: async (data) => {
      setMessage(`借阅申请已提交，凭取书码 ${data.voucher_code} 到服务台取书，24 小时内有效。`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["borrow-list"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["book-search"] }),
        queryClient.invalidateQueries({ queryKey: ["book-copies"] }),
      ]);
    },
    onError: (error) => {
      setMessage(error instanceof Error ? error.message : "借阅服务暂不可用");
    },
  });

  function updateParams(updates: Record<string, string>) {
    const next = new URLSearchParams(params);
    Object.entries(updates).forEach(([key, value]) => setOrDelete(next, key, value));
    next.delete("offset");
    setOffset(0);
    setParams(next);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    const next = input.trim();
    if (next) void bookApi.recordSearchEvent(next);
    updateParams({ query: next });
  }

  function clearFilters() {
    setInput("");
    setSelected(null);
    setOffset(0);
    setParams({});
  }

  function handlePageChange(nextOffset: number) {
    setOffset(nextOffset);
    const next = new URLSearchParams(params);
    if (nextOffset > 0) next.set("offset", String(nextOffset));
    else next.delete("offset");
    setParams(next);
  }

  function selectBook(book: BookItem) {
    setSelected(book);
    setSelectedCopyId(null);
    setDetailBook(book);
  }

  function promptCopySelection(book: BookItem) {
    setSelected(book);
    setSelectedCopyId(null);
    setDetailBook(book);
    setMessage("请先在图书详情里选择具体副本，再借阅或定位。");
  }

  function selectCopy(copy: BookCopy) {
    setSelectedCopyId(copy.id);
    setTimeout(() => {
      mapRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  }

  function borrowCopy(copy: BookCopy) {
    const bookId = copy.book_id ?? detailBook?.id ?? selectedBook?.id;
    if (!bookId) {
      setMessage("缺少图书信息，无法提交借阅申请。");
      return;
    }
    borrowMutation.mutate({ bookId, copyId: copy.id });
  }

  function locateCopy(copy: BookCopy) {
    if (detailBook) setSelected(detailBook);
    setSelectedCopyId(copy.id);
    setDetailBook(null);
    setTimeout(() => mapRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
  }

  return (
    <main className="user-page search-page">
      <section className="search-main-grid">
        <div className="search-main-column">
          <form className="big-search search-page__search" onSubmit={handleSubmit}>
            <Search size={27} />
            <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="搜索书名、作者、分类码、主题词" />
            <button className="primary-button" type="submit">搜索</button>
          </form>
          <FlowFeedback message={message} />


          <GlassCard className="search-results">
            <div className="search-results__topline">
              <div className="section-heading section-heading--stacked">
                <h2>图书结果</h2>
                <span>{books.data?.total !== undefined ? `共找到 ${books.data.total} 条结果` : "暂无结果统计"}</span>
              </div>
              <button className="search-clear" type="button" onClick={clearFilters}>
                <RotateCcw size={16} />
                清空筛选
              </button>
            </div>

            <div className="search-filter-bar" aria-label="找书筛选条件">
              <div className="filter-tabs">
                <button type="button" className={`filter-chip ${!availability ? "filter-chip--active" : ""}`} onClick={() => updateParams({ availability: "" })}>全部</button>
                <button type="button" className={`filter-chip ${availability === "available" ? "filter-chip--active" : ""}`} onClick={() => updateParams({ availability: "available" })}>可借</button>
                <button type="button" className={`filter-chip ${availability === "unavailable" || availability === "none" ? "filter-chip--active" : ""}`} onClick={() => updateParams({ availability: "unavailable" })}>暂不可借</button>
              </div>
              <div className="filter-selects">
                <label className="filter-select filter-select--real">
                  <Filter size={15} />
                  <select value={category} onChange={(event) => updateParams({ category: event.target.value })}>
                    <option value="">全部分类</option>
                    {categories.map((item) => {
                      const code = item.code || item.category_code || String(item.id || "");
                      return <option key={code} value={code}>{item.name}</option>;
                    })}
                  </select>
                </label>
                <label className="filter-select filter-select--real">
                  <Filter size={15} />
                  <select value={zone} onChange={(event) => updateParams({ zone: event.target.value })}>
                    <option value="">全部区域</option>
                    {zones.map((item) => {
                      const code = item.zone_code || item.code || String(item.id || item.zone_id || "");
                      const name = item.zone_name || item.name || code;
                      return <option key={code} value={code}>{name}</option>;
                    })}
                  </select>
                </label>
                <label className="filter-select filter-select--real">
                  <Filter size={15} />
                  <select value={floor} onChange={(event) => updateParams({ floor: event.target.value })}>
                    <option value="">全部楼层</option>
                    {floors.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label className="filter-select filter-select--real">
                  <SlidersHorizontal size={15} />
                  <select value={sort} onChange={(event) => updateParams({ sort: event.target.value })}>
                    <option value="availability">可借优先</option>
                    <option value="newest">出版年优先</option>
                    <option value="title">书名排序</option>
                  </select>
                </label>
              </div>
            </div>

            {books.isLoading ? <div className="skeleton-list" /> : items.length ? (
              <div className="book-list">
                {items.map((book) => (
                  <BookListItem
                    key={book.id}
                    book={book}
                    onSelect={selectBook}
                    onLocate={promptCopySelection}
                    onBorrow={promptCopySelection}
                    onReserve={(item) => reserveMutation.mutate(item)}
                    reserveDisabled={!session || reserveMutation.isPending || borrowMutation.isPending}
                    borrowPending={borrowMutation.isPending}
                  />
                ))}
              </div>
            ) : (
              <div className="search-empty-wrap">
                <EmptyState title="暂无图书结果" description={books.isError ? "数据暂不可用" : "请输入检索条件后查看馆藏结果"} />
              </div>
            )}
            <Pagination total={books.data?.total} limit={books.data?.limit} offset={books.data?.offset} onPageChange={handlePageChange} />
          </GlassCard>
        </div>

        <aside className="right-rail search-right-rail" ref={mapRef}>
          <GlassCard className="rail-card rail-card--map">
            <LibraryMapCard book={selectedBook} copies={copyItems} selectedCopy={selectedCopy} initialFloor={targetFloor || floor} onSelectCopy={selectCopy} />
          </GlassCard>
        </aside>
      </section>
      <ReaderBookDetailDialog
        bookId={detailBook?.id}
        fallbackBook={detailBook}
        open={Boolean(detailBook)}
        onClose={() => setDetailBook(null)}
        onReserve={(book) => reserveMutation.mutate(book)}
        onBorrow={borrowCopy}
        onSelectCopy={(copy) => {
          if (detailBook) setSelected(detailBook);
          setSelectedCopyId(copy.id);
        }}
        onLocateCopy={locateCopy}
        reserveDisabled={!session || reserveMutation.isPending}
        reservePending={reserveMutation.isPending}
        borrowPending={borrowMutation.isPending}
      />
    </main>
  );
}
