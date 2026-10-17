import { getData, getTokenKey, postData } from "@/services/http";
import { clearReaderSession, setReaderSession } from "@/services/readerApi";
import type { ReaderProfile } from "@/types/user";

export type LoginPayload = {
  account: string;
  password: string;
  remember?: boolean;
};

export type RegisterPayload = {
  name: string;
  email: string;
  phone: string;
  code: string;
  password: string;
  confirmPassword: string;
  accepted: boolean;
};

export type ResetPasswordPayload = {
  account: string;
  code: string;
  password: string;
  confirmPassword: string;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  reader: ReaderProfile;
};

type VerificationCodeResponse = {
  sent: boolean;
  local_debug?: boolean;
  debug_code?: string;
  masked_account?: string;
  expires_in_seconds?: number;
};

export const userAuthApi = {
  login: async (payload: LoginPayload) => {
    const data = await postData<LoginResponse, LoginPayload>("/reader-auth/login", payload);
    localStorage.setItem(getTokenKey(), data.access_token);
    setReaderSession({
      reader_code: data.reader.reader_code ?? undefined,
      name: data.reader.name ?? undefined,
    });
    return data;
  },
  me: () => getData<ReaderProfile>("/reader-auth/me"),
  logout: async () => {
    try {
      await postData("/reader-auth/logout");
    } finally {
      localStorage.removeItem(getTokenKey());
      clearReaderSession();
    }
  },
  register: async (payload: RegisterPayload) => {
    const data = await postData<LoginResponse, RegisterPayload>("/reader-auth/register", payload);
    localStorage.setItem(getTokenKey(), data.access_token);
    setReaderSession({
      reader_code: data.reader.reader_code ?? undefined,
      name: data.reader.name ?? undefined,
    });
    return data;
  },
  requestVerificationCode: (account: string, purpose?: string) => postData<VerificationCodeResponse, { account: string; purpose?: string }>("/reader-auth/verification-code", { account, purpose }),
  resetPassword: (payload: ResetPasswordPayload) => postData<{ success: boolean }, ResetPasswordPayload>("/reader-auth/reset-password", payload),
};
