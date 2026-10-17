import type { BookItem } from "@/types/book";
import type { ReaderProfile } from "@/types/user";

export type BorrowRecord = {
  loan_id?: number;
  renewal_count?: number | null;
  max_renewals?: number | null;
  can_renew?: boolean | null;
  renew_blocked_reason?: string | null;
  reader_code?: string | null;
  reader_name?: string | null;
  reader?: ReaderProfile | null;
  book_code?: string | null;
  title?: string | null;
  author?: string | null;
  cover_url?: string | null;
  book?: BookItem | null;
  copy_code?: string | null;
  copy?: {
    id?: number;
    copy_code?: string | null;
    status?: string | null;
    copy_status?: string | null;
  } | null;
  borrowed_at?: string | null;
  due_at?: string | null;
  returned_at?: string | null;
  status?: string | null;
  overdue_days?: number | null;
  location?: string | null;
};

export type BorrowSummary = {
  current: number | null;
  dueSoon: number | null;
  overdue: number | null;
  renewable: number | null;
  reservationCount?: number | null;
  creditScore?: number | null;
};
