import type { BookItem, CategoryOption } from "@/types/book";
import type { BorrowRecord, BorrowSummary } from "@/types/borrow";
import type { NotificationItem } from "@/types/notification";
import type { ReaderBorrowSummary } from "@/types/user";

export type LibraryProfile = {
  name?: string | null;
  library_name?: string | null;
  address?: string | null;
  opening_hours?: string | null;
  phone?: string | null;
  service_phone?: string | null;
  service_email?: string | null;
  library_type?: string | null;
  open_floors?: string | null;
  reading_seat_count?: number | null;
  image_url?: string | null;
};

export type HomeOverview = {
  categories: CategoryOption[];
  recommendations: BookItem[];
  notifications: NotificationItem[];
  library: LibraryProfile | null;
  borrowSummary: BorrowSummary;
  dueSoon: BorrowRecord[];
  readerSummary: ReaderBorrowSummary | null;
  unavailable: boolean;
};
