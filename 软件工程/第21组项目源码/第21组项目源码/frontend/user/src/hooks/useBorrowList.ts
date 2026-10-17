import { useQuery } from "@tanstack/react-query";
import { borrowApi } from "@/services/borrowApi";

export function useBorrowList(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["borrow-list", params],
    queryFn: () => borrowApi.getCurrentBorrows(params),
  });
}

export function useBorrowSummary() {
  return useQuery({
    queryKey: ["borrow-summary"],
    queryFn: borrowApi.getBorrowSummary,
  });
}

export function useBorrowReminders() {
  return useQuery({
    queryKey: ["borrow-reminders"],
    queryFn: borrowApi.getDueReminders,
  });
}
