import { getData, postData, type ApiList } from "@/services/http";
import type { BorrowRecord, BorrowSummary } from "@/types/borrow";

export const borrowApi = {
  getBorrowSummary: () => getData<BorrowSummary>("/reader/borrows/summary"),
  getCurrentBorrows: async (params?: { status?: string; limit?: number; offset?: number }): Promise<ApiList<BorrowRecord>> => {
    return getData<ApiList<BorrowRecord>>("/reader/borrows", {
      status: params?.status,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    });
  },
  getDueReminders: () => getData<BorrowRecord[]>("/reader/borrows/due-reminders"),
  getBorrowRules: () => getData<unknown | null>("/reader/borrow-rules"),
  renewBorrow: (loanId: number) => postData<unknown>(`/reader/borrows/${loanId}/renew`),
  returnBorrow: (loanId: number) => postData<{ request_code: string; voucher_code: string; status: string; expires_at?: string | null }>(`/reader/borrows/${loanId}/return`),
  requestBorrow: (payload: { book_id?: number; copy_id?: number; hold_hours?: number }) => postData<{ request_code: string; voucher_code: string; status: string }>("/reader/borrows/request", payload),
};
