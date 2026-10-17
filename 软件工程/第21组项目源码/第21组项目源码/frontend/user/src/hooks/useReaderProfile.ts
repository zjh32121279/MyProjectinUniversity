import { useQuery } from "@tanstack/react-query";
import { getReaderSession, readerApi } from "@/services/readerApi";

export function useReaderProfile() {
  const session = getReaderSession();
  return useQuery({
    queryKey: ["reader-profile"],
    queryFn: readerApi.getProfile,
    enabled: Boolean(session?.reader_code),
  });
}

export function useProfileCenter() {
  const session = getReaderSession();
  return useQuery({
    queryKey: ["profile-center"],
    queryFn: readerApi.getProfileCenter,
    enabled: Boolean(session?.reader_code),
  });
}
