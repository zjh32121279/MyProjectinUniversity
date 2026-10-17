import { getData } from "@/api/http";
import type { AnyRecord } from "@/types/api";

export const rulesApi = {
  borrow: () => getData<{ items: AnyRecord[] }>("/rules/borrow"),
};
