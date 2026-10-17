import { getData, http, postData, putData } from "@/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const aiApi = {
  status: (params?: QueryParams) => getData<AnyRecord>("/ai/engine/status", params),
  conversations: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/ai/conversations", params),
  createConversation: (body?: { title?: string }) => postData<AnyRecord>("/ai/conversations", body ?? {}),
  conversationMessages: (conversationCode: string, params?: QueryParams) => getData<ApiList<AnyRecord>>(`/ai/conversations/${conversationCode}/messages`, params),
  renameConversation: (conversationCode: string, title: string) => putData<AnyRecord>(`/ai/conversations/${conversationCode}`, { title }),
  deleteConversation: (conversationCode: string) => http.delete(`/ai/conversations/${conversationCode}`) as Promise<AnyRecord>,
  chat: (body: { conversation_id: string; text: string }) => http.post("/ai/chat", body, { timeout: 120000 }) as Promise<AnyRecord>,
};
