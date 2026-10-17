import { useQuery } from "@tanstack/react-query";
import { homeApi } from "@/services/homeApi";

export function useHomeOverview() {
  return useQuery({
    queryKey: ["home-overview"],
    queryFn: homeApi.getHomeOverview,
  });
}
