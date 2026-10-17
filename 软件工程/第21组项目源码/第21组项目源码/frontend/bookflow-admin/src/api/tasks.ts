import { getData, postData } from "@/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const tasksApi = {
  list: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/tasks", params),
  detail: (taskCode: string) => getData<AnyRecord>(`/tasks/${taskCode}`),
  create: (body: AnyRecord) => postData<AnyRecord>("/tasks", body),
  claim: (taskCode: string, body: AnyRecord) => postData<AnyRecord>(`/tasks/${taskCode}/claim`, body),
  resolve: (taskCode: string, body: AnyRecord) => postData<AnyRecord>(`/tasks/${taskCode}/resolve`, body),
  cancel: (taskCode: string, body: AnyRecord) => postData<AnyRecord>(`/tasks/${taskCode}/cancel`, body),
};
