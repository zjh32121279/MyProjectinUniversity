import { getData, postData, putData, uploadFile } from "@/services/http";
import type { BorrowHistoryItem, ProfileCenter, ReaderBorrowSummary, ReaderPreferences, ReaderProfile, ReaderSession } from "@/types/user";

export const SESSION_KEY = "bookflow_user_session";

export function getReaderSession(): ReaderSession | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ReaderSession;
    return parsed.reader_code ? parsed : null;
  } catch {
    return null;
  }
}

export function setReaderSession(session: ReaderSession) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearReaderSession() {
  localStorage.removeItem(SESSION_KEY);
}

export const readerApi = {
  getProfile: () => getData<ReaderProfile>("/reader/me"),
  getProfileCenter: () => getData<ProfileCenter>("/reader/profile-center"),
  updateContact: (body: { phone?: string; email?: string }) => putData<ReaderProfile, { phone?: string; email?: string }>("/reader/profile/contact", body),
  changePassword: (body: { old_password: string; new_password: string; confirm_password: string }) =>
    putData<{ changed: boolean }, { old_password: string; new_password: string; confirm_password: string }>("/reader/profile/password", body),
  submitFeedback: (body: { category?: string; content: string }) => postData<{ submitted: boolean }, { category?: string; content: string }>("/reader/profile/feedback", body),
  getReaderStats: () => getData<Record<string, number | null>>("/reader/stats"),
  getBorrowRules: () => getData<unknown | null>("/reader/borrow-rules"),
  getReservationRules: () => getData<unknown | null>("/reader/reservation-rules"),
  getBorrowSummary: () => getData<ReaderBorrowSummary>("/reader/borrows/summary"),
  getPreferences: () => getData<ReaderPreferences>("/reader/preferences"),
  updatePreferences: (body: { favorite_category_codes?: string[]; recommendation_source?: string }) =>
    putData<ReaderPreferences, { favorite_category_codes?: string[]; recommendation_source?: string }>("/reader/preferences", body),
  getBorrowHistory: (limit = 50, offset = 0) => getData<BorrowHistoryItem[]>(`/reader/borrows/history?limit=${limit}&offset=${offset}`),
  uploadAvatar: (file: File) => uploadFile<ReaderProfile>("/reader/profile/avatar", file, "file"),
};
