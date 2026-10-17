import { getData } from "@/api/http";
import type { AnyRecord } from "@/types/api";

export const analyticsApi = {
  overview: () => getData<AnyRecord>("/analytics/overview"),
  collectionHealth: () => getData<AnyRecord>("/analytics/collection-health"),
  circulation: () => getData<AnyRecord>("/analytics/circulation"),
  readers: () => getData<AnyRecord>("/analytics/readers"),
  aiEfficiency: () => getData<AnyRecord>("/analytics/ai-efficiency"),
  tasks: () => getData<AnyRecord>("/analytics/tasks"),
  brief: () => getData<AnyRecord>("/analytics/brief"),
};
