import { SharedLoginView } from "@common/login/SharedLoginView";
import { formatErrorCode } from "@common/utils/format";
import { useLogin } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";

export function LoginPage() {
  const token = useAuthStore((state) => state.token);
  const admin = useAuthStore((state) => state.admin);
  const login = useLogin();

  return (
    <SharedLoginView
      token={admin?.is_super_admin ? token : null}
      redirectTo="/super-admin/home"
      isPending={login.isPending}
      errorMessage={login.isError ? formatErrorCode((login.error as { code?: string }).code || login.error.message) || "登录失败，请检查账号或密码。" : undefined}
      onSubmit={(account, password) => login.mutate({ account, password })}
    />
  );
}
