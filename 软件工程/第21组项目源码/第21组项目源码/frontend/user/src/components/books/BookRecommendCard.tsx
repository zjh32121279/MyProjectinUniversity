import { BookCover } from "@/components/common/BookCover";
import type { BookItem } from "@/types/book";

type BookRecommendCardProps = {
  book: BookItem;
  onOpen?: (book: BookItem) => void;
};

export function BookRecommendCard({ book, onOpen }: BookRecommendCardProps) {
  return (
    <button className="recommend-card" type="button" onClick={() => onOpen?.(book)}>
      <BookCover src={book.cover_url} title={book.title} />
      <h3>{book.title || "—"}</h3>
      <p>{book.author || "—"}</p>
    </button>
  );
}
