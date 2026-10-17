import { getData, postData } from "@/api/http";
import type { AnyRecord, ApiList, QueryParams } from "@/types/api";

export const circulationApi = {
  loans: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/circulation/borrow-records", params),
  borrow: (body: { reader_code: string; copy_code: string }) => postData<AnyRecord>("/circulation/borrow", body),
  returnCopy: (body: { copy_code: string }) => postData<AnyRecord>("/circulation/return", body),
  serviceRequest: (requestCode: string) => getData<AnyRecord>(`/circulation/requests/${encodeURIComponent(requestCode)}`),
  completeBorrowRequest: (requestCode: string, voucherCode?: string) => postData<AnyRecord>(`/circulation/requests/${encodeURIComponent(requestCode)}/borrow/complete`, voucherCode ? { voucher_code: voucherCode } : undefined),
  completeReturnRequest: (requestCode: string) => postData<AnyRecord>(`/circulation/requests/${encodeURIComponent(requestCode)}/return/complete`),
  cancelRequest: (requestCode: string) => postData<AnyRecord>(`/circulation/requests/${encodeURIComponent(requestCode)}/cancel`),
  renew: (body: { loan_id: number }) => postData<AnyRecord>("/circulation/renew", body),
  createReservation: (body: { reader_code: string; book_code: string }) => postData<AnyRecord>("/circulation/reservations", body),
  pendingRequests: (params?: QueryParams) => getData<ApiList<AnyRecord>>("/circulation/pending-requests", params),
  borrowingState: (params: QueryParams) => getData<AnyRecord>("/admin/circulation/operation-state", params),
};
