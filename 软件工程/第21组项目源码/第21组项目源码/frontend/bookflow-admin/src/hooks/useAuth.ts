import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { login, logout, me } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export function useCurrentAdmin(enabled = true) {
  const setAdmin = useAuthStore((state) => state.setAdmin);
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: me,
    enabled,
    retry: false,
    staleTime: 60_000,
    meta: {
      onSuccess: setAdmin,
    },
  });
}

export function useLogin() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      setSession(data.access_token, data.admin);
      queryClient.setQueryData(["auth", "me"], data.admin);
      navigate("/admin/home", { replace: true });
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
