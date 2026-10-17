import { getData, http } from "@/services/http";

export type ReaderAIActionField = {
  label: string;
  value: string;
};

export type ReaderAIAction = {
  kind: string;
  request_type?: string;
  status?: string;
  title: string;
  summary?: string;
  fields?: ReaderAIActionField[];
};

export type ReaderAIChatResponse = {
  answer: string;
  actions?: ReaderAIAction[];
  service_requests?: unknown[];
  tool_scope?: string[];
  task_code?: string;
  kernel_run_id?: string;
};

export const aiApi = {
  getSuggestions: () => getData<string[]>("/reader-ai/suggestions"),
  chat: (message: string, history: Array<{ role: string; content: string }> = []) =>
    http.post("/reader-ai/chat", { message, history }, { timeout: 120000 }) as Promise<ReaderAIChatResponse>,
};
