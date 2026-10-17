import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { getReaderSession } from "@/services/readerApi";

type RequireReaderProps = {
  children: ReactNode;
};

export function RequireReader({ children }: RequireReaderProps) {
  const location = useLocation();
  const session = getReaderSession();

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
