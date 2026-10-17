import { useQuery } from "@tanstack/react-query";
import { notificationApi } from "@/services/notificationApi";

export function useNotifications(params?: { status?: string; type?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["notifications", params],
    queryFn: () => notificationApi.getNotifications(params),
  });
}

export function useNotificationSummary() {
  return useQuery({
    queryKey: ["notification-summary"],
    queryFn: notificationApi.getNotificationSummary,
  });
}

export function useNotificationSettings() {
  return useQuery({
    queryKey: ["notification-settings"],
    queryFn: notificationApi.getNotificationSettings,
  });
}
