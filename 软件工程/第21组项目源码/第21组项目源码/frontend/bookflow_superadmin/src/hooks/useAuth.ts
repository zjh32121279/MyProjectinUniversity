import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { login, logout, me } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export function useCurrentAdmin(enabled = true) {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: me,
    enabled,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      if (!data.admin.is_super_admin) {
        toast.error("当前账号不是超级管理员，请使用超级管理员账号登录。");
        return;
      }
      setSession(data.access_token, data.admin);
      queryClient.setQueryData(["auth", "me"], data.admin);
      navigate("/super-admin/home", { replace: true });
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clear = useAuthStore((state) => state.clear);

  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      clear();
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
}
