import { SharedLoginView } from "@common/login/SharedLoginView";
import { useLogin } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import { formatErrorCode } from "@/utils/labels";

export function LoginPage() {
  const token = useAuthStore((state) => state.token);
  const login = useLogin();

  return (
    <SharedLoginView
      token={token}
      redirectTo="/admin/home"
      isPending={login.isPending}
      errorMessage={login.isError ? formatErrorCode((login.error as { code?: string }).code) || "登录失败，请检查账号或密码。" : undefined}
      onSubmit={(account, password) => login.mutate({ account, password })}
    />
  );
}
