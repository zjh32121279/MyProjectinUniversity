import { useQuery } from "@tanstack/react-query";
import { aiApi } from "@/api/ai";
import { AIChatPanel } from "@/components/ai/AIChatPanel";
import { ErrorState } from "@/components/ui/ErrorState";

export function AIWorkbenchPage() {
  const status = useQuery({ queryKey: ["ai", "status"], queryFn: () => aiApi.status({ probe: true }) });

  if (status.isError) return <ErrorState onRetry={() => void status.refetch()} />;

  const engineStatus = status.data ?? {};
  const engineConfigured = Boolean(engineStatus.connected ?? engineStatus.available ?? engineStatus.ok ?? engineStatus.enabled ?? engineStatus.configured);

  return (
    <div className="bf-page-shell">
      <AIChatPanel engineConfigured={engineConfigured} engineStatus={engineStatus} onRefreshStatus={() => void status.refetch()} />
    </div>
  );
}
