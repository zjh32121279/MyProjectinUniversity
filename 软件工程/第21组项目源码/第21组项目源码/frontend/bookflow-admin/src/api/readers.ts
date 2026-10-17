import { getData, postData, putData } from "@/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const readersApi = {
  list: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/readers", params),
  detail: (readerCode: string) => getData<AnyRecord>(`/readers/${readerCode}`),
  activity: (readerCode: string) => getData<AnyRecord>(`/readers/${readerCode}/activity`),
  recentActivity: (limit = 20) => getData<{ items: AnyRecord[] }>("/readers/recent-activity", { limit }),
  create: (body: AnyRecord) => postData<AnyRecord>("/readers", body),
  update: (readerCode: string, body: AnyRecord) => putData<AnyRecord>(`/readers/${readerCode}`, body),
  suspend: (readerCode: string, reason = "manual_suspend") => postData<AnyRecord>(`/readers/${readerCode}/suspend`, { reason }),
  restore: (readerCode: string, reason = "manual_restore") => postData<AnyRecord>(`/readers/${readerCode}/restore`, { reason }),
  resetPassword: (readerCode: string, newPassword: string, confirmPassword: string) => postData<AnyRecord>(`/readers/${readerCode}/reset-password`, { new_password: newPassword, confirm_password: confirmPassword }),
};
