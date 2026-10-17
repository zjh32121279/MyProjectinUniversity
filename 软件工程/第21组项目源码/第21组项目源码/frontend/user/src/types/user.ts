import type { BorrowRecord } from "@/types/borrow";
import type { ReservationRecord } from "@/types/reservation";

export type ReaderSession = {
  reader_code?: string;
  name?: string;
  avatar_url?: string;
};

export type ReaderProfile = {
  id?: number;
  reader_code?: string | null;
  name?: string | null;
  reader_type_code?: string | null;
  reader_type_name?: string | null;
  phone_masked?: string | null;
  email?: string | null;
  credit_score?: number | null;
  status?: string | null;
  borrow_suspended_until?: string | null;
  borrow_suspended?: boolean | null;
  avatar_url?: string | null;
  status_name?: string | null;
  registered_at?: string | null;
  current_borrow_count?: number | null;
  max_borrow_count?: number | null;
  credit_status?: string | null;
};

export type ReaderBorrowSummary = {
  reader?: ReaderProfile | null;
  current_borrows?: BorrowRecord[];
  historical_borrows?: BorrowRecord[];
  current_overdues?: BorrowRecord[];
  reservations?: ReservationRecord[];
  credit_events?: ProfileCenterItem[];
};

export type ProfileCenterItem = {
  label: string;
  value: string | number | boolean | null;
  description?: string | null;
};

export type ProfileCenterAction = {
  type: "contact_form" | "password_form" | "feedback_form" | "navigate" | string;
  label: string;
  to?: string;
};

export type ProfileCenterSection = {
  key: string;
  group: string;
  title: string;
  summary: string;
  items: ProfileCenterItem[];
  actions: ProfileCenterAction[];
};

export type ProfileCenter = {
  profile: ReaderProfile;
  summary: Record<string, string | number | boolean | null | undefined>;
  sections: ProfileCenterSection[];
};

export type ReaderPreferences = {
  favorite_category_codes: string[];
  recommendation_source: "popular" | "preference" | "both";
};

export type BorrowHistoryItem = BorrowRecord & {
  loan_id: number;
  book_id: number;
  title: string;
  author?: string;
  cover_url?: string;
  borrowed_at?: string | null;
  returned_at?: string | null;
  due_at?: string | null;
  status: string;
};
