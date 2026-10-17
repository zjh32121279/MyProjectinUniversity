import { getData, putData } from "@/api/http";
import type { AnyRecord } from "@/types/api";

export const libraryApi = {
  profile: () => getData<AnyRecord>("/library/profile"),
  updateProfile: (body: AnyRecord) => putData<AnyRecord>("/library/profile", body),
  updateSpaceConfig: (body: AnyRecord) => putData<AnyRecord>("/library/space-config", body),
  updateSettings: (body: AnyRecord) => putData<AnyRecord>("/library/settings", body),
};
