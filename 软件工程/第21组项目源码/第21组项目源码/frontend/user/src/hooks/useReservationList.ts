import { useQuery } from "@tanstack/react-query";
import { reservationApi } from "@/services/reservationApi";

export function useReservationList(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["reservation-list", params],
    queryFn: () => reservationApi.getReservations(params),
  });
}

export function useReservationSummary() {
  return useQuery({
    queryKey: ["reservation-summary"],
    queryFn: reservationApi.getReservationSummary,
  });
}

export function usePickupReminders() {
  return useQuery({
    queryKey: ["pickup-reminders"],
    queryFn: reservationApi.getPickupReminders,
  });
}
