import { getData, postData, putData } from "@/api/http";
import { http } from "@common/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const locationsApi = {
  tree: () => getData<AnyRecord>("/locations/tree"),
  zones: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/locations/zones", params),
  shelves: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/locations/shelves", params),
  positions: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/locations/positions", params),

  // zone CRUD
  createZone: (body: AnyRecord) => postData<AnyRecord>("/locations/zones", body),
  updateZone: (zoneId: number, body: AnyRecord) => putData<AnyRecord>(`/locations/zones/${zoneId}`, body),
  deleteZone: (zoneId: number) => http.delete(`/locations/zones/${zoneId}`).then(() => undefined),

  // shelf CRUD
  createShelf: (body: AnyRecord) => postData<AnyRecord>("/locations/shelves", body),
  updateShelf: (shelfId: number, body: AnyRecord) => putData<AnyRecord>(`/locations/shelves/${shelfId}`, body),
  deleteShelf: (shelfId: number) => http.delete(`/locations/shelves/${shelfId}`).then(() => undefined),

  // layout batch save
  saveLayout: (body: { zones: AnyRecord[]; shelves: AnyRecord[] }) => postData<AnyRecord>("/locations/layout", body),
  applyBookFlowDefaultLayout: () => postData<AnyRecord>("/locations/layout/bookflow-default", {}),
};
