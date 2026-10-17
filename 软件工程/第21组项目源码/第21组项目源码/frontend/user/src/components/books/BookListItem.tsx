import { BookOpen, FileText } from "lucide-react";
import { BookCover } from "@/components/common/BookCover";
import { StatusBadge } from "@/components/common/StatusBadge";
import type { BookItem } from "@/types/book";

type BookListItemProps = {
  book: BookItem;
  onSelect?: (book: BookItem) => void;
  onLocate?: (book: BookItem) => void;
  onReserve?: (book: BookItem) => void;
  onBorrow?: (book: BookItem) => void;
  reserveDisabled?: boolean;
  borrowPending?: boolean;
};

function availabilityText(available: number | null, total: number | null) {
  if (available === null) return "暂无统计";
  if (available > 0) return `可借 ${available}${total ? ` / 共 ${total}` : ""}`;
  return total ? `暂无可借 / 共 ${total}` : "暂无可借";
}

export function BookListItem({ book, onSelect, onLocate, onReserve, onBorrow, reserveDisabled, borrowPending }: BookListItemProps) {
  const available = book.available_copies ?? book.copy_stats?.available ?? null;
  const total = book.total_copies ?? null;
  const reserved = book.reserved_copies ?? book.copy_stats?.reserved ?? 0;
  const unavailable = book.unavailable_copies ?? book.copy_stats?.unavailable ?? 0;
  const zone = book.primary_zone?.zone_name || book.primary_zone?.zone_code || "—";

  return (
    <article className="book-list-item" onClick={() => onSelect?.(book)}>
      <span onClick={(e) => e.stopPropagation()}>
        <BookCover src={book.cover_url} title={book.title} compact />
      </span>
      <div className="book-list-item__main">
        <h3>{book.title || "—"}</h3>
        <p>{book.author || "—"} / {book.publisher || "—"}</p>
        <small>{[book.category_name, book.subcategory_name].filter(Boolean).join(" / ") || "—"}</small>
      </div>
      <div className="book-list-item__meta book-list-item__meta--code">
        <span>图书编号</span>
        <strong>{book.book_code || "—"}</strong>
      </div>
      <div className="book-list-item__meta">
        <span>馆藏位置</span>
        <strong title={zone}>{zone}</strong>
      </div>
      <div className="book-list-item__meta">
        <span>馆藏状态</span>
        <strong>{availabilityText(available, total)}</strong>
        <em>{reserved ? `预约 ${reserved}` : unavailable ? `不可借 ${unavailable}` : "状态正常"}</em>
      </div>
      <div className="book-list-item__actions" onClick={(event) => event.stopPropagation()}>
        <StatusBadge status={available && available > 0 ? "available" : undefined} />
        <button type="button" onClick={() => onSelect?.(book)} title="查看详情" aria-label="查看详情">
          <FileText size={14} />
          <span className="book-action-text">详情</span>
        </button>
        <span className="book-list-item__hint"><BookOpen size={13} />点击行可查看位置</span>
      </div>
    </article>
  );
}
