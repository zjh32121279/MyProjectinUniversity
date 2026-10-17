import axios, { AxiosError } from "axios";

const TOKEN_KEY = "bookflow_user_token";

export type AnyRecord = Record<string, unknown>;

export type ApiList<T = AnyRecord> = {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
  empty_state?: boolean;
};

export type QueryParams = Record<string, string | number | boolean | undefined | null>;

type ApiErrorPayload = {
  code: string;
  message: string;
  details?: AnyRecord;
};

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
  error?: ApiErrorPayload;
};

export class BookFlowApiError extends Error {
  code: string;
  details?: AnyRecord;
  status?: number;

  constructor(payload: ApiErrorPayload, status?: number) {
    super(payload.message || payload.code);
    this.name = "BookFlowApiError";
    this.code = payload.code;
    this.details = payload.details;
    this.status = status;
  }
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 3500,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => {
    const envelope = response.data as ApiEnvelope<unknown>;
    if (envelope && envelope.success === true) {
      return envelope.data;
    }
    if (envelope?.error) {
      throw new BookFlowApiError(envelope.error, response.status);
    }
    return response.data;
  },
  (error: AxiosError<ApiEnvelope<unknown>>) => {
    const body = error.response?.data as (ApiEnvelope<unknown> & Partial<ApiErrorPayload>) | undefined;
    const payload = body?.error ?? (body?.code ? { code: body.code, message: body.message || body.code, details: body.details } : undefined);
    if (payload) {
      throw new BookFlowApiError(payload, error.response?.status);
    }
    if (error.code === "ECONNABORTED") {
      throw new BookFlowApiError({
        code: "REQUEST_TIMEOUT",
        message: "请求处理超时，请稍后查看结果或缩小问题范围后重试",
      });
    }
    throw new BookFlowApiError({
      code: "NETWORK_ERROR",
      message: "数据暂不可用",
    });
  },
);

export function getTokenKey() {
  return TOKEN_KEY;
}

export async function getData<T>(url: string, params?: QueryParams): Promise<T> {
  return http.get(url, { params }) as Promise<T>;
}

export async function postData<T, B = unknown>(url: string, body?: B): Promise<T> {
  return http.post(url, body) as Promise<T>;
}

export async function putData<T, B = unknown>(url: string, body?: B): Promise<T> {
  return http.put(url, body) as Promise<T>;
}

export async function deleteData<T>(url: string): Promise<T> {
  return http.delete(url) as Promise<T>;
}

export async function uploadFile<T>(url: string, file: File, fieldName = "file"): Promise<T> {
  const form = new FormData();
  form.append(fieldName, file);
  const token = localStorage.getItem(TOKEN_KEY);
  const { data } = await axios.post<ApiEnvelope<T>>(
    `${http.defaults.baseURL}${url}`,
    form,
    {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "Content-Type": "multipart/form-data",
      },
    },
  );
  if (data.success === true) return data.data as T;
  if (data.error) throw new BookFlowApiError(data.error);
  return data as unknown as T;
}
