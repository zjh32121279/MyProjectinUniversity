import type { BookItem } from "@/types/book";
import type { ReaderProfile } from "@/types/user";

export type ReservationRecord = {
  reservation_id?: number;
  reader?: ReaderProfile | null;
  book?: BookItem | null;
  copy?: {
    id?: number;
    copy_code?: string | null;
  } | null;
  status?: string | null;
  reserved_until?: string | null;
  created_at?: string | null;
  queue_position?: number | null;
  pickup_code_available?: boolean;
};

export type ReservationSummary = {
  active: number | null;
  ready: number | null;
  expiring: number | null;
  history: number | null;
};
