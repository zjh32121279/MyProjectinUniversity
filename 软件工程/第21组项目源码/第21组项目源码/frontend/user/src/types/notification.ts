/** 投递记录 —— 对应后端 NotificationDelivery 模型 */
export type NotificationItem = {
  id: number;
  delivery_code?: string | null;
  message_id?: number | null;
  title?: string | null;
  content?: string | null;
  notification_type?: string | null;
  recipient_type?: string | null;
  recipient_id?: number | null;
  channel?: string | null;
  delivery_status?: string | null;
  read_status?: "unread" | "read" | null;
  sent_at?: string | null;
  read_at?: string | null;
  related_entity_type?: string | null;
  related_entity_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type NotificationSummary = {
  total: number;
  unread: number;
  byType: Record<string, number>;
};

export type NotificationSettings = {
  enabled?: boolean;
  items?: Array<{
    key: string;
    label: string;
    enabled: boolean;
    mutable: boolean;
  }>;
};
