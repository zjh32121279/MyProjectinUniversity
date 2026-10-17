import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Toaster, toast } from "sonner";
import { BookFlowApiError } from "@common/api/http";

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof BookFlowApiError && error.code !== "AUTH_INVALID_TOKEN") {
        toast.error(error.message);
      }
    },
  }),
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof BookFlowApiError && error.status && error.status < 500) {
          return false;
        }
        return failureCount < 1;
      },
    },
  },
});

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
}
