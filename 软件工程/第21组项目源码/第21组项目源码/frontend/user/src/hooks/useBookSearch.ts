import { useQuery } from "@tanstack/react-query";
import { bookApi } from "@/services/bookApi";
import type { BookSearchParams } from "@/types/book";

export function useBookSearch(params: BookSearchParams) {
  return useQuery({
    queryKey: ["book-search", params],
    queryFn: () => bookApi.searchBooks(params),
  });
}

export function useBookFilters() {
  return useQuery({
    queryKey: ["book-filter-options"],
    queryFn: bookApi.getFilterOptions,
  });
}

export function useBookDetail(bookId?: number | null) {
  return useQuery({
    queryKey: ["book-detail", bookId],
    queryFn: () => bookApi.getBookDetail(Number(bookId)),
    enabled: Boolean(bookId),
  });
}

export function useBookCopies(bookId?: number | null) {
  return useQuery({
    queryKey: ["book-copies", bookId],
    queryFn: () => bookApi.getBookCopies(Number(bookId), 20),
    enabled: Boolean(bookId),
  });
}

export function useHotKeywords() {
  return useQuery({
    queryKey: ["hot-keywords"],
    queryFn: () => bookApi.getHotKeywords(),
  });
}
