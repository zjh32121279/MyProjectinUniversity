import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { dashboardApi } from "@/api/dashboard";

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard", "admin"], queryFn: dashboardApi.admin });
}

export function useAnalyticsBrief() {
  return useQuery({ queryKey: ["analytics", "brief"], queryFn: analyticsApi.brief });
}
