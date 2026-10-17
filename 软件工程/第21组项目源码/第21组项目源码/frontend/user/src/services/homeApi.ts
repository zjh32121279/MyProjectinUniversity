import { getData } from "@/services/http";
import { bookApi } from "@/services/bookApi";
import { getReaderSession } from "@/services/readerApi";
import type { BookItem } from "@/types/book";
import type { HomeOverview, LibraryProfile } from "@/types/home";

async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch {
    return fallback;
  }
}

export const homeApi = {
  getLibraryProfile: async () => getData<LibraryProfile | null>("/public/library/profile"),
  getHomeOverview: async (): Promise<HomeOverview> => {
    const session = getReaderSession();
    if (session) {
      const data = await getData<{
        library: LibraryProfile | null;
        categories: HomeOverview["categories"];
        recommendations: BookItem[];
        recent_notifications: HomeOverview["notifications"];
        borrow_summary: { current_count: number; due_this_week: number; reservation_count: number; credit_score: number | null };
        due_soon: HomeOverview["dueSoon"];
      }>("/reader/home");
      return {
        categories: data.categories ?? [],
        recommendations: data.recommendations ?? [],
        notifications: data.recent_notifications ?? [],
        library: data.library ?? null,
        borrowSummary: {
          current: data.borrow_summary?.current_count ?? 0,
          dueSoon: data.borrow_summary?.due_this_week ?? 0,
          reservationCount: data.borrow_summary?.reservation_count ?? 0,
          creditScore: data.borrow_summary?.credit_score ?? null,
          overdue: null,
          renewable: null,
        },
        dueSoon: data.due_soon ?? [],
        readerSummary: null,
        unavailable: false,
      };
    }
    const [categories, recommendations, library] = await Promise.all([
      safe(() => bookApi.getCategoryOptions(), []),
      safe(async () => {
        const data = await bookApi.hotBooks(12);
        return data.items ?? [];
      }, [] as BookItem[]),
      safe(() => homeApi.getLibraryProfile(), null),
    ]);
    return {
      categories,
      recommendations,
      notifications: [],
      library,
      borrowSummary: { current: null, dueSoon: null, overdue: null, renewable: null, reservationCount: null, creditScore: null },
      dueSoon: [],
      readerSummary: null,
      unavailable: false,
    };
  },
};
