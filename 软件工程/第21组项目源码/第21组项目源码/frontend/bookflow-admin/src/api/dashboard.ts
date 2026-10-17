import { getData } from "@/api/http";
import type { AnyRecord } from "@/types/api";

export const dashboardApi = {
  admin: () => getData<AnyRecord>("/dashboard/admin"),
};
