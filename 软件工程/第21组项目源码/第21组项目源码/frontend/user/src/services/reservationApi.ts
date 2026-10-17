import { getData, postData, type ApiList } from "@/services/http";
import type { ReservationRecord, ReservationSummary } from "@/types/reservation";

export const reservationApi = {
  getReservationSummary: () => getData<ReservationSummary>("/reader/reservations/summary"),
  getReservations: async (params?: { status?: string; limit?: number; offset?: number }): Promise<ApiList<ReservationRecord>> => {
    return getData<ApiList<ReservationRecord>>("/reader/reservations", {
      status: params?.status,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    });
  },
  getPickupReminders: () => getData<ReservationRecord[]>("/reader/reservations/pickup-reminders"),
  getReservationRules: () => getData<unknown | null>("/reader/reservation-rules"),
  createReservation: (payload: { book_id?: number; copy_id?: number }) => postData<unknown, { book_id?: number; copy_id?: number }>("/reader/reservations", payload),
  cancelReservation: (reservationId: number) => postData<unknown>(`/reader/reservations/${reservationId}/cancel`),
  getPickupCode: (reservationId: number) => getData<unknown | null>(`/reader/reservations/${reservationId}/pickup-code`),
};
