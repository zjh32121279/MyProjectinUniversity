export type AnyRecord = Record<string, unknown>;

export type ApiList<T = AnyRecord> = {
  items: T[];
  total?: number;
  limit?: number;
  offset?: number;
  empty_state?: boolean;
};

export type ApiErrorPayload = {
  code: string;
  message: string;
  details?: AnyRecord;
};

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string | null;
  error?: ApiErrorPayload;
};

export type QueryParams = Record<string, string | number | boolean | undefined | null>;
