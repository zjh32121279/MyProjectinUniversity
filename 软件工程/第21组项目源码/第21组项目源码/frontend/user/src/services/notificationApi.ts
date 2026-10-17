import { deleteData, getData, postData, putData, type ApiList } from "@/services/http";
import type { NotificationItem, NotificationSettings, NotificationSummary } from "@/types/notification";
import { getReaderSession } from "@/services/readerApi";

const EMPTY_LIST: ApiList<NotificationItem> = { items: [], total: 0, limit: 20, offset: 0, empty_state: true };

export const notificationApi = {
  getLatestNotifications: async (limit = 4): Promise<NotificationItem[]> => {
    const session = getReaderSession();
    if (!session?.reader_code) return [];
    const data = await getData<ApiList<NotificationItem>>("/reader/notifications", {
      limit,
      offset: 0,
    });
    return data.items ?? [];
  },

  getNotifications: async (
    params?: { status?: string; type?: string; limit?: number; offset?: number }
  ): Promise<ApiList<NotificationItem>> => {
    const session = getReaderSession();
    if (!session?.reader_code) return EMPTY_LIST;
    return getData<ApiList<NotificationItem>>("/reader/notifications", {
      status: params?.status,
      type: params?.type,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    });
  },

  getNotificationSummary: async (): Promise<NotificationSummary | null> => {
    const session = getReaderSession();
    if (!session?.reader_code) return null;
    return getData<NotificationSummary>("/reader/notifications/summary");
  },

  getNotificationOverview: async () => notificationApi.getNotificationSummary(),

  getNotificationSettings: async (): Promise<NotificationSettings | null> =>
    getData<NotificationSettings | null>("/reader/notification-settings"),

  updateNotificationSettings: async (key: string, enabled: boolean) =>
    putData<NotificationSettings, { key: string; enabled: boolean }>(
      "/reader/notification-settings",
      { key, enabled }
    ),

  /** 标记单条投递为已读（按 delivery id） */
  markRead: async (deliveryId: number) =>
    postData<NotificationItem>(`/reader/notifications/${deliveryId}/read`),

  /** 全部标为已读 */
  markAllRead: async () => postData<unknown>("/reader/notifications/read-all"),

  /** 清空已读 —— 归档投递记录，不删除消息 */
  clearRead: async () => deleteData<unknown>("/reader/notifications/read"),
};
