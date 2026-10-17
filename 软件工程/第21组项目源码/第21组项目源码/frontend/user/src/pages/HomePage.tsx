import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BookOpenCheck, CalendarClock, Library, MapPin, Phone, Search, ShieldCheck, Timer } from "lucide-react";
import { BookRecommendCard } from "@/components/books/BookRecommendCard";
import { ReaderBookDetailDialog } from "@/components/books/ReaderBookDetail";
import { CategoryPill } from "@/components/common/CategoryPill";
import { EmptyState } from "@/components/common/EmptyState";
import { GlassCard } from "@/components/common/GlassCard";
import { StatCard } from "@/components/common/StatCard";
import { useHomeOverview } from "@/hooks/useHomeOverview";
import { getReaderSession } from "@/services/readerApi";
import { borrowApi } from "@/services/borrowApi";
import { reservationApi } from "@/services/reservationApi";
import type { BookCopy, BookItem } from "@/types/book";
import { formatDate } from "@/utils/formatDate";

function cleanLibraryType(value?: string | null) {
  const text = (value || "").replace(/小型/g, "").trim();
  return text || "公共图书馆";
}

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [recommendPage, setRecommendPage] = useState(0);
  const [categoryPage, setCategoryPage] = useState(0);
  const [detailBook, setDetailBook] = useState<BookItem | null>(null);
  const overview = useHomeOverview();
  const data = overview.data;
  const library = data?.library;
  const session = getReaderSession();
  const categories = data?.categories ?? [];
  const categoryPageCount = Math.max(1, Math.ceil(categories.length / 6));
  const visibleCategories = useMemo(() => {
    if (categories.length <= 6) return categories;
    const start = (categoryPage % categoryPageCount) * 6;
    const batch = categories.slice(start, start + 6);
    return batch.length === 6 ? batch : [...batch, ...categories.slice(0, 6 - batch.length)];
  }, [categories, categoryPage, categoryPageCount]);
  const recommendations = data?.recommendations ?? [];
  const recommendPageCount = Math.max(1, Math.ceil(recommendations.length / 4));
  const visibleRecommendations = useMemo(() => {
    if (recommendations.length <= 4) return recommendations;
    const start = (recommendPage % recommendPageCount) * 4;
    const batch = recommendations.slice(start, start + 4);
    return batch.length === 4 ? batch : [...batch, ...recommendations.slice(0, 4 - batch.length)];
  }, [recommendPage, recommendPageCount, recommendations]);

  const reserveMutation = useMutation({
    mutationFn: (book: BookItem) => reservationApi.createReservation({ book_id: book.id }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["reservation-list"] }),
        queryClient.invalidateQueries({ queryKey: ["reservation-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["book-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["book-copies"] }),
      ]);
    },
  });

  const borrowMutation = useMutation({
    mutationFn: ({ bookId, copyId }: { bookId: number; copyId: number }) => borrowApi.requestBorrow({ book_id: bookId, copy_id: copyId }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["borrow-list"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["book-copies"] }),
      ]);
    },
  });

  function borrowCopy(copy: BookCopy) {
    const bookId = copy.book_id ?? detailBook?.id;
    if (!bookId) return;
    borrowMutation.mutate({ bookId, copyId: copy.id });
  }

  function locateCopy(copy: BookCopy) {
    const bookId = copy.book_id ?? detailBook?.id;
    const next = new URLSearchParams();
    const keyword = detailBook?.title || copy.title || "";

    if (keyword) next.set("query", keyword);
    if (bookId) next.set("book_id", String(bookId));
    next.set("copy_id", String(copy.id));
    if (copy.location?.floor) next.set("target_floor", copy.location.floor);

    navigate(`/search?${next.toString()}`);
  }

  useEffect(() => {
    if (recommendations.length <= 4) return undefined;
    const timer = window.setInterval(() => {
      setRecommendPage((value) => (value + 1) % recommendPageCount);
    }, 4200);
    return () => window.clearInterval(timer);
  }, [recommendPageCount, recommendations.length]);

  useEffect(() => {
    setRecommendPage(0);
  }, [recommendations.length]);

  useEffect(() => {
    if (categories.length <= 6) return undefined;
    const timer = window.setInterval(() => {
      setCategoryPage((value) => (value + 1) % categoryPageCount);
    }, 3600);
    return () => window.clearInterval(timer);
  }, [categories.length, categoryPageCount]);

  useEffect(() => {
    setCategoryPage(0);
  }, [categories.length]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate(`/search${query.trim() ? `?query=${encodeURIComponent(query.trim())}` : ""}`);
  }

  return (
    <main className="user-page home-page">
      <section className="home-board">
        <section className="home-hero">
          <h1>今天想读点什么？</h1>
          <p>搜索好书、预约馆藏，BookFlow AI 随时为你帮忙。</p>
          <form className="big-search" onSubmit={handleSearch}>
            <Search size={28} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索书名、作者、分类码、主题词" />
            <button className="primary-button" type="submit">搜索</button>
          </form>
          <div className="category-carousel">
            {visibleCategories.length ? (
              <div className="category-row">
                {visibleCategories.map((category) => (
                  <CategoryPill key={`${category.id ?? category.code ?? category.name}`} label={category.name} code={category.code} onClick={() => navigate(`/search?category=${encodeURIComponent(category.code || String(category.id || ""))}`)} />
                ))}
              </div>
            ) : (
              <span className="muted-inline">暂无分类</span>
            )}
            {categoryPageCount > 1 ? (
              <div className="category-dots" aria-label="分类批次">
                {Array.from({ length: categoryPageCount }).map((_, index) => (
                  <button key={index} type="button" className={index === categoryPage % categoryPageCount ? "is-active" : ""} onClick={() => setCategoryPage(index)} aria-label={`第 ${index + 1} 批分类`} />
                ))}
              </div>
            ) : null}
          </div>
        </section>

        <aside className="home-side-column">
          <GlassCard className="home-summary">
            <div className="section-heading">
              <h2>我的借阅</h2>
            </div>
            <div className="stat-grid stat-grid--home">
              <StatCard icon={<BookOpenCheck size={21} />} label="当前借阅" value={data?.borrowSummary.current} />
              <StatCard icon={<CalendarClock size={21} />} label="本周到期" value={data?.borrowSummary.dueSoon} tone="orange" />
              <StatCard icon={<BookOpenCheck size={21} />} label="预约中" value={data?.borrowSummary.reservationCount} tone="purple" />
              <StatCard icon={<ShieldCheck size={21} />} label="信用分" value={data?.borrowSummary.creditScore} tone="green" />
            </div>
          </GlassCard>

          <GlassCard className="home-due">
            <div className="section-heading">
              <h2>即将到期</h2>
            </div>
            {data?.dueSoon.length ? (
              <div className="due-list">
                {data.dueSoon.slice(0, 3).map((item) => (
                  <article key={item.loan_id}>
                    <strong>{item.title || item.book?.title || "—"}</strong>
                    <span>{formatDate(item.due_at)}</span>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="暂无借阅记录" />
            )}
          </GlassCard>
        </aside>

        <section className="home-bottom-grid">
          <GlassCard className="home-recommend">
            <div className="section-heading">
              <h2>为你推荐</h2>
            </div>
            {overview.isLoading ? <div className="skeleton-row" /> : data?.recommendations.length ? (
              <div className="recommend-carousel">
                <div className="recommend-grid" aria-live="polite">
                  {visibleRecommendations.map((book) => <BookRecommendCard key={book.id} book={book} onOpen={setDetailBook} />)}
                </div>
                {recommendPageCount > 1 ? (
                  <div className="recommend-dots" aria-label="推荐批次">
                    {Array.from({ length: recommendPageCount }).map((_, index) => (
                      <button key={index} type="button" className={index === recommendPage % recommendPageCount ? "is-active" : ""} onClick={() => setRecommendPage(index)} aria-label={`第 ${index + 1} 批推荐`} />
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <EmptyState title="暂无推荐内容" />
            )}
          </GlassCard>

          <GlassCard className="home-notices">
            <div className="section-heading">
              <h2>最近通知</h2>
            </div>
            {data?.notifications.length ? (
              <div className="notice-list">
                {data.notifications.slice(0, 4).map((item) => (
                  <article key={item.id}>
                    <Bell size={17} />
                    <strong>{item.title || "—"}</strong>
                    <span>{formatDate(item.created_at)}</span>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="暂无通知" />
            )}
          </GlassCard>

          <GlassCard className="home-library home-library--synced">
            <div className="section-heading">
              <h2>图书馆信息</h2>
            </div>
            {library ? (
              <div className="library-info library-info--rich">
                <div className="library-info__title">
                  <Library size={28} />
                  <div>
                    <strong>{library.name || library.library_name || "—"}</strong>
                    <span>{cleanLibraryType(library.library_type)}</span>
                  </div>
                </div>
                <p><MapPin size={16} />{library.address || "—"}</p>
                <p><Timer size={16} />{library.opening_hours || "—"}</p>
                <p><Phone size={16} />{library.phone || library.service_phone || "—"}</p>
              </div>
            ) : (
              <EmptyState title="暂无图书馆信息" />
            )}
          </GlassCard>
        </section>
      </section>
      <ReaderBookDetailDialog
        bookId={detailBook?.id}
        fallbackBook={detailBook}
        open={Boolean(detailBook)}
        onClose={() => setDetailBook(null)}
        onReserve={(book) => reserveMutation.mutate(book)}
        onBorrow={borrowCopy}
        onSelectCopy={(copy) => {}}
        onLocateCopy={locateCopy}
        reserveDisabled={!session || reserveMutation.isPending || borrowMutation.isPending}
        reservePending={reserveMutation.isPending}
        borrowPending={borrowMutation.isPending}
      />
    </main>
  );
}
