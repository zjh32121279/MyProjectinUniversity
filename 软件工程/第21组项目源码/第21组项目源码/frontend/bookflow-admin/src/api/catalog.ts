import { getData, postData, putData } from "@/api/http";
import { http } from "@common/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const catalogApi = {
  books: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/catalog/books", params),
  categories: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/catalog/categories", params),
  subcategories: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/catalog/subcategories", params),
  bookDetail: (bookId: number) => getData<AnyRecord>(`/catalog/books/${bookId}`),
  copies: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/catalog/copies", params),
  bookCopies: (bookId: number, params?: QueryParams) => getData<ApiList<AnyRecord>>(`/catalog/books/${bookId}/copies`, params),
  createBook: (body: AnyRecord) => postData<AnyRecord>("/catalog/books", body),
  updateBook: (bookId: number, body: AnyRecord) => putData<AnyRecord>(`/catalog/books/${bookId}`, body),
  uploadBookCover: (bookId: number, file: File) => {
    const form = new FormData();
    form.append("file", file, file.name || "cover");
    return http.post(`/catalog/books/${bookId}/cover`, form, { timeout: 30000 }) as Promise<AnyRecord>;
  },
  createCopies: (bookId: number, body: AnyRecord) => postData<AnyRecord>(`/catalog/books/${bookId}/copies`, body),
  updateCopyStatus: (copyId: number, body: AnyRecord) => putData<AnyRecord>(`/catalog/copies/${copyId}/status`, body),
  updateCopyLocation: (copyId: number, body: AnyRecord) => putData<AnyRecord>(`/catalog/copies/${copyId}/location`, body),

  // category CRUD
  createCategory: (body: AnyRecord) => postData<AnyRecord>("/catalog/categories", body),
  updateCategory: (categoryId: number, body: AnyRecord) => putData<AnyRecord>(`/catalog/categories/${categoryId}`, body),
  deleteCategory: (categoryId: number) => http.delete(`/catalog/categories/${categoryId}`).then(() => undefined),

  // subcategory CRUD
  createSubcategory: (body: AnyRecord) => postData<AnyRecord>("/catalog/subcategories", body),
  updateSubcategory: (subcategoryId: number, body: AnyRecord) => putData<AnyRecord>(`/catalog/subcategories/${subcategoryId}`, body),
  deleteSubcategory: (subcategoryId: number) => http.delete(`/catalog/subcategories/${subcategoryId}`).then(() => undefined),
};
