import { getData, postData, type ApiList } from "@/services/http";
import type { BookCopy, BookFilterOptions, BookItem, BookSearchParams, CategoryOption } from "@/types/book";

export const bookApi = {
  searchBooks: (params?: BookSearchParams) => getData<ApiList<BookItem>>("/public/catalog/books", params),
  getBookDetail: (bookId: number) => getData<BookItem>(`/public/catalog/books/${bookId}`),
  getBookCopies: (bookId: number, limit = 20) => getData<ApiList<BookCopy>>(`/public/catalog/books/${bookId}/copies`, { limit, offset: 0 }),
  getAvailability: (bookId: number) => getData<Record<string, unknown>>(`/public/catalog/books/${bookId}/availability`),
  getCategories: () => getData<CategoryOption[]>("/public/catalog/categories"),
  getFilterOptions: () => getData<BookFilterOptions>("/public/catalog/filter-options"),
  getHotKeywords: () => getData<Array<{ keyword: string; count: number }>>("/public/search/hot-keywords"),
  getLocationTree: () => getData<{ items: Record<string, unknown>[]; total?: number; empty_state?: boolean }>("/public/locations/map"),
  recordSearchEvent: (keyword: string) => postData<unknown, { keyword: string }>("/public/search/events", { keyword }),
  hotBooks: async (limit = 8) => getData<ApiList<BookItem>>("/public/catalog/books", { sort: "popular", circulation_type: "热门", limit, offset: 0 }),
  coldBooks: async (limit = 8) => getData<ApiList<BookItem>>("/public/catalog/books", { limit, offset: 0 }),
  bookCopies: (bookId: number, limit = 20) => getData<ApiList<BookCopy>>(`/public/catalog/books/${bookId}/copies`, { limit, offset: 0 }),
  getCategoryOptions: () => getData<CategoryOption[]>("/public/catalog/categories"),
};
