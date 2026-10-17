import { getData, postData } from "@/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const notificationsApi = {
  list: (params?: QueryParams) =>
    getData<ApiList<AnyRecord> & { stats: AnyRecord }>("/notifications", params),
  stats: () => getData<AnyRecord>("/notifications/stats"),
  recipientOptions: (params?: QueryParams) =>
    getData<ApiList<AnyRecord>>("/notifications/recipient-options", params),
  batch: (body: AnyRecord) => postData<AnyRecord>("/notifications/batch", body),
  sendMessage: (messageId: number) =>
    postData<AnyRecord>(`/notifications/${messageId}/send`),
  cancelMessage: (messageId: number) =>
    postData<AnyRecord>(`/notifications/${messageId}/cancel`),
};
