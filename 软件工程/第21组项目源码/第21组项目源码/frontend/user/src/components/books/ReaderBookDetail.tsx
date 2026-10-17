import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, LocateFixed, MapPin, ShoppingCart, X } from "lucide-react";
import { useBookCopies, useBookDetail } from "@/hooks/useBookSearch";
import { BookCover } from "@/components/common/BookCover";
import { EmptyState } from "@/components/common/EmptyState";
import type { BookCopy, BookItem } from "@/types/book";

type ReaderBookDetailPanelProps = {
  book?: BookItem | null;
  copies?: BookCopy[];
  selectedCopy?: BookCopy | null;
  onSelectCopy?: (copy: BookCopy) => void;
  onLocateCopy?: (copy: BookCopy) => void;
  onReserve?: (book: BookItem) => void;
  onBorrow?: (copy: BookCopy) => void;
  reserveDisabled?: boolean;
  reservePending?: boolean;
  borrowPending?: boolean;
};

type ReaderBookDetailDialogProps = {
  bookId?: number | null;
  fallbackBook?: BookItem | null;
  open: boolean;
  onClose: () => void;
  onReserve?: (book: BookItem) => void;
  onBorrow?: (copy: BookCopy) => void;
  onSelectCopy?: (copy: BookCopy) => void;
  onLocateCopy?: (copy: BookCopy) => void;
  reserveDisabled?: boolean;
  reservePending?: boolean;
  borrowPending?: boolean;
};

function text(value: unknown, fallback = "—") {
  return String(value ?? "").trim() || fallback;
}

function copyStatus(copy?: BookCopy | null) {
  const status = String(copy?.copy_status ?? copy?.status ?? "").trim();
  const labels: Record<string, string> = {
    available: "可借",
    borrowed: "已借出",
    reserved: "预约保留",
    maintenance: "维护中",
    unavailable: "暂不可借",
  };
  return labels[status] || status || "状态未知";
}

function isAvailable(copy?: BookCopy | null) {
  return String(copy?.copy_status ?? copy?.status ?? "") === "available";
}

function normalizeFloor(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw.toUpperCase().startsWith("F") ? raw.toUpperCase() : `F${raw}`;
}

function sideFromPosition(positionCode?: string | null) {
  if (!positionCode) return "";
  const last = positionCode.split("-").pop() || "";
  if (["左", "右", "L", "R", "left", "right"].includes(last)) return last;
  if (last.toUpperCase() === "L" || last === "左") return "左";
  if (last.toUpperCase() === "R" || last === "右") return "右";
  return "";
}

export function copyLocation(copy?: BookCopy | null) {
  if (!copy) return "暂无副本位置";
  const loc = copy.location;
  const floor = normalizeFloor(loc?.floor);
  const zone = [loc?.zone_code, loc?.zone_name].filter(Boolean).join("");
  const shelf = loc?.shelf_code;
  const side = sideFromPosition(loc?.position_code || loc?.shelf_position);
  const parts = [floor, zone, shelf].filter(Boolean);
  if (!parts.length) return "暂无副本位置";
  let result = parts.join("-");
  if (side) result += `-${side}`;
  return result;
}

export function ReaderBookDetailPanel({ book, copies = [], selectedCopy, onSelectCopy, onLocateCopy, onReserve, onBorrow, reserveDisabled, reservePending, borrowPending }: ReaderBookDetailPanelProps) {
  const availableCopies = copies.filter(isAvailable);
  const activeCopy = selectedCopy ?? null;
  const hasAvailable = availableCopies.length > 0 || Number(book?.available_copies ?? 0) > 0;

  if (!book) {
    return <EmptyState title="请选择图书" description="点击图书结果后查看详情和馆藏位置" />;
  }

  return (
    <section className="reader-book-detail reader-book-detail--showcase">
      <div className="reader-book-detail__cover-stage">
        <BookCover src={book.cover_url} title={book.title} />
        <span className={hasAvailable ? "reader-book-detail__availability reader-book-detail__availability--available" : "reader-book-detail__availability"}>
          {hasAvailable ? "可借" : "可预约"}
        </span>
      </div>

      <div className="reader-book-detail__content">
        <div className="reader-book-detail__title-block">
          <span>{[book.category_name, book.subcategory_name].filter(Boolean).join(" / ") || "未分类"}</span>
          <h2>{text(book.title)}</h2>
          <p>{text(book.author)} / {text(book.publisher)}</p>
        </div>

        <p className="reader-book-detail__intro">{text(book.introduction, "暂无简介")}</p>

        <div className="reader-book-detail__fact-grid">
          <span><strong>{Number(book.available_copies ?? 0)}</strong>可借副本</span>
          <span><strong>{Number(book.total_copies ?? 0)}</strong>馆藏总数</span>
          <span><strong>{activeCopy ? copyStatus(activeCopy) : "未选择"}</strong>当前副本</span>
          <span><strong>{text(book.publish_year)}</strong>出版年份</span>
          <span><strong>{text(book.book_code)}</strong>图书编号</span>
          <span><strong>{text(book.isbn)}</strong>ISBN</span>
          <span><strong>{text(book.call_number)}</strong>索书号</span>
          <span><strong>{activeCopy ? copyLocation(activeCopy) : "选择副本后显示"}</strong>馆藏位置</span>
        </div>

        {!hasAvailable ? (
          <div className="reader-book-detail__primary-action">
            <div><CalendarPlus size={18} /><span>当前暂无可借副本，可以预约排队。</span></div>
            <button type="button" disabled={reserveDisabled || reservePending} onClick={() => onReserve?.(book)}><CalendarPlus size={16} />{reservePending ? "提交中" : "预约"}</button>
          </div>
        ) : null}
      </div>

      <div className="reader-book-detail__copies">
        <div className="reader-book-detail__section-title">
          <strong>副本与位置</strong>
          <span>{copies.length ? `${copies.length} 册` : "暂无副本"}</span>
        </div>
        {copies.length ? copies.map((copy) => {
          const active = activeCopy?.id === copy.id;
          const available = isAvailable(copy);
          return (
            <article key={copy.id} className={active ? "reader-copy-row reader-copy-row--active" : "reader-copy-row"}>
              <button className="reader-copy-row__select" type="button" onClick={() => onSelectCopy?.(copy)}>
                <span>
                  <strong>{copy.copy_code || `副本 ${copy.id}`}</strong>
                  <em>{copyLocation(copy)}</em>
                </span>
                <i className={available ? "reader-copy-status reader-copy-status--available" : "reader-copy-status"}>{copyStatus(copy)}</i>
              </button>
              <div className="reader-copy-row__actions">
                <button type="button" onClick={() => (onLocateCopy ? onLocateCopy(copy) : onSelectCopy?.(copy))}>
                  <LocateFixed size={14} />定位
                </button>
                {onBorrow ? (
                  <button type="button" className="reader-copy-row__borrow" disabled={reserveDisabled || borrowPending || !available} onClick={() => onBorrow(copy)}>
                    <ShoppingCart size={14} />借阅
                  </button>
                ) : null}
              </div>
            </article>
          );
        }) : (
          <EmptyState title="暂无副本信息" description="系统尚未返回可定位副本" />
        )}
      </div>
    </section>
  );
}

export function ReaderBookDetailDialog({ bookId, fallbackBook, open, onClose, onReserve, onBorrow, onSelectCopy, onLocateCopy, reserveDisabled, reservePending, borrowPending }: ReaderBookDetailDialogProps) {
  const detail = useBookDetail(open ? bookId : null);
  const book = detail.data ?? fallbackBook ?? null;
  const copies = useBookCopies(open ? book?.id : null);
  const copyItems = copies.data?.items ?? book?.sample_copies ?? [];
  const [selectedCopyId, setSelectedCopyId] = useState<number | null>(null);
  const selectedCopy = useMemo(
    () => copyItems.find((copy) => copy.id === selectedCopyId) ?? null,
    [copyItems, selectedCopyId],
  );

  useEffect(() => {
    setSelectedCopyId(null);
  }, [book?.id]);

  if (!open) return null;

  return (
    <div className="reader-detail-dialog" role="dialog" aria-modal="true" aria-label="图书详情">
      <div className="reader-detail-dialog__backdrop" onClick={onClose} />
      <div className="reader-detail-dialog__panel reader-detail-dialog__panel--book">
        <div className="reader-detail-dialog__header">
          <div>
            <MapPin size={18} />
            <strong>图书详情</strong>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭详情"><X size={20} /></button>
        </div>
        {detail.isLoading ? (
          <div className="skeleton-list" />
        ) : (
          <ReaderBookDetailPanel
            book={book}
            copies={copyItems}
            selectedCopy={selectedCopy}
            onSelectCopy={(copy) => { setSelectedCopyId(copy.id); onSelectCopy?.(copy); }}
            onLocateCopy={(copy) => { setSelectedCopyId(copy.id); onLocateCopy?.(copy); }}
            onReserve={onReserve}
            onBorrow={onBorrow}
            reserveDisabled={reserveDisabled}
            reservePending={reservePending}
            borrowPending={borrowPending}
          />
        )}
      </div>
    </div>
  );
}
