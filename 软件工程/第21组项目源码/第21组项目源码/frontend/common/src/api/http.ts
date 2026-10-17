import axios, { AxiosError } from "axios";

const TOKEN_KEY = "bookflow_admin_token";

export type AnyRecord = Record<string, unknown>;

export type ApiList<T = AnyRecord> = {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
  empty_state?: boolean;
};

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

export type QueryParams = Record<string, string | number | boolean | undefined | null>;

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
  timeout: 18000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let _isRefreshing = false;
let _refreshPromise: Promise<void> | null = null;

async function _tryRefreshToken(): Promise<boolean> {
  if (_isRefreshing && _refreshPromise) {
    await _refreshPromise;
    return true;
  }
  _isRefreshing = true;
  _refreshPromise = (async () => {
    try {
      const res = await http.post("/auth/refresh");
      const data = res as unknown as { access_token: string };
      if (data.access_token) {
        localStorage.setItem(TOKEN_KEY, data.access_token);
      }
    } catch {
      // refresh failed — token is truly expired
    } finally {
      _isRefreshing = false;
      _refreshPromise = null;
    }
  })();
  await _refreshPromise;
  return !!localStorage.getItem(TOKEN_KEY);
}

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
  async (error: AxiosError<ApiEnvelope<unknown>>) => {
    // Try token refresh on 401 — skip for auth endpoints to avoid deadlock
    const retryConfig = error.config as (typeof error.config & { _retried?: boolean }) | undefined;
    const isAuthEndpoint = retryConfig?.url && /\/auth\/(login|refresh)$/.test(retryConfig.url);
    if (error.response?.status === 401 && retryConfig && !retryConfig._retried && !isAuthEndpoint) {
      retryConfig._retried = true;
      const ok = await _tryRefreshToken();
      if (ok) {
        // Retry the original request with new token
        const newToken = localStorage.getItem(TOKEN_KEY);
        if (newToken) {
          retryConfig.headers.Authorization = `Bearer ${newToken}`;
        }
        return http.request(retryConfig);
      }
    }
    const payload = error.response?.data?.error;
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
      message: error.message || "网络请求失败",
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
