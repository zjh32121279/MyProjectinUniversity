import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BookOpenCheck, CalendarClock, CheckCheck, Mail, Megaphone, MessageCircle, SlidersHorizontal, Trash2, X } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { FlowFeedback } from "@/components/common/FlowFeedback";
import { GlassCard } from "@/components/common/GlassCard";
import { Pagination } from "@/components/common/Pagination";
import { StatCard } from "@/components/common/StatCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useNotificationSettings, useNotificationSummary, useNotifications } from "@/hooks/useNotifications";
import { notificationApi } from "@/services/notificationApi";
import type { NotificationItem } from "@/types/notification";
import { formatDateTime } from "@/utils/formatDate";

const notificationSettingLabels: Record<string, string> = {
  borrow_due_enabled: "借阅到期提醒",
  reservation_arrival_enabled: "预约到书提醒",
  system_notice_enabled: "系统通知",
  email_enabled: "邮件通知",
  sms_enabled: "短信通知",
};

function notificationSettingLabel(key: string, fallback?: string | null) {
  return notificationSettingLabels[key] || fallback || "通知设置";
}

export function NotificationPage() {
  const queryClient = useQueryClient();
  const pageSize = 8;
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const [selectedType, setSelectedType] = useState<string | undefined>(undefined);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [detailItem, setDetailItem] = useState<NotificationItem | null>(null);
  const summary = useNotificationSummary();
  const notifications = useNotifications({
    limit: pageSize,
    offset,
    type: selectedType,
    status: onlyUnread ? "unread" : undefined,
  });
  const settings = useNotificationSettings();
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-settings"] }),
    ]);
  };
  const markRead = useMutation({
    mutationFn: notificationApi.markRead,
    onSuccess: refresh,
    onError: (error) =>
      setMessage(error instanceof Error ? error.message : "通知服务暂不可用"),
  });
  const markAll = useMutation({
    mutationFn: notificationApi.markAllRead,
    onSuccess: refresh,
    onError: (error) =>
      setMessage(error instanceof Error ? error.message : "通知服务暂不可用"),
  });
  const clearRead = useMutation({
    mutationFn: notificationApi.clearRead,
    onSuccess: refresh,
    onError: (error) =>
      setMessage(error instanceof Error ? error.message : "通知服务暂不可用"),
  });
  const updateSetting = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      notificationApi.updateNotificationSettings(key, enabled),
    onSuccess: refresh,
    onError: (error) =>
      setMessage(error instanceof Error ? error.message : "消息设置服务暂不可用"),
  });
  const items = notifications.data?.items ?? [];

  const tabs = [
    { key: "all", label: "全部", value: summary.data?.total, type: undefined },
    { key: "due", label: "借阅提醒", value: summary.data?.byType?.due, type: "due" },
    { key: "reservation", label: "预约通知", value: summary.data?.byType?.reservation, type: "reservation" },
    { key: "system", label: "系统消息", value: summary.data?.byType?.system, type: "system" },
    { key: "activity", label: "活动公告", value: summary.data?.byType?.activity, type: "activity" },
  ];

  return (
    <main className="user-page user-flow-page notification-page">
      <section className="page-title flow-title">
        <h1>通知中心</h1>
        <p>查看系统提醒、借阅动态与预约通知。仅显示已发送的通知。</p>
      </section>

      <section className="notification-tabs notification-tabs--refined" aria-label="通知分类">
        <FlowFeedback message={message} />
        {tabs.map((tab) => (
          <button
            className={selectedType === tab.type ? "is-active" : ""}
            key={tab.key}
            type="button"
            onClick={() => {
              setSelectedType(tab.type);
              setOffset(0);
              setMessage("");
            }}
          >
            {tab.label}
            {tab.value != null ? <span>{tab.value}</span> : null}
          </button>
        ))}
        <button
          className={onlyUnread ? "notification-filter is-active" : "notification-filter"}
          type="button"
          onClick={() => {
            setOnlyUnread((value) => !value);
            setOffset(0);
            setMessage("");
          }}
        >
          <SlidersHorizontal size={16} />
          {onlyUnread ? "全部" : "未读"}
        </button>
      </section>

      <section className="flow-layout notification-layout">
        <GlassCard className="records-card flow-records-card notification-records-card">
          <div className="flow-card-header">
            <div>
              <h2>消息列表</h2>
              <span>
                {notifications.isLoading
                  ? "加载中"
                  : items.length
                    ? `${items.length} 条消息`
                    : "暂无消息"}
              </span>
            </div>
          </div>
          {items.length ? (
            <div className="notification-list refined-notification-list">
              {items.map((item) => {
                const isRead = item.read_status === "read";
                return (
                  <article
                    key={item.id}
                    className="notification-item--clickable"
                    onClick={() => setDetailItem(item)}
                  >
                    <Bell size={20} />
                    <div>
                      <h3>{item.title || "—"}</h3>
                      <p>{item.content || "—"}</p>
                    </div>
                    <time>{formatDateTime(item.created_at)}</time>
                    <StatusBadge status={isRead ? "read" : "unread"} />
                    <button
                      type="button"
                      disabled={isRead || markRead.isPending}
                      onClick={(e) => {
                        e.stopPropagation();
                        markRead.mutate(item.id);
                      }}
                    >
                      {isRead ? "已读" : "标为已读"}
                    </button>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="notification-empty-zone">
              <EmptyState
                title="暂无通知"
                description={
                  notifications.isError ? "数据暂不可用" : "当前账号没有可显示的通知"
                }
              />
            </div>
          )}
          <Pagination
            total={notifications.data?.total}
            limit={notifications.data?.limit ?? pageSize}
            offset={notifications.data?.offset ?? offset}
            onPageChange={setOffset}
          />
        </GlassCard>

        <aside className="right-rail flow-right-rail notification-right-rail">
          <GlassCard className="flow-side-card notification-overview-card">
            <div className="flow-card-header flow-card-header--compact">
              <div>
                <h2>消息概览</h2>
                <span>{summary.data ? "已连接" : "暂无数据"}</span>
              </div>
            </div>
            <div className="stat-grid stat-grid--compact notification-mini-stats">
              <StatCard
                icon={<MessageCircle size={22} />}
                label="未读消息"
                value={summary.data?.unread}
              />
              <StatCard
                icon={<Megaphone size={22} />}
                label="全部消息"
                value={summary.data?.total}
                tone="orange"
              />
              <StatCard
                icon={<BookOpenCheck size={22} />}
                label="借阅提醒"
                value={summary.data?.byType?.due ?? null}
                tone="green"
              />
              <StatCard
                icon={<CalendarClock size={22} />}
                label="预约通知"
                value={summary.data?.byType?.reservation ?? null}
                tone="purple"
              />
            </div>
          </GlassCard>

          <GlassCard className="flow-side-card notification-settings-card">
            <div className="flow-card-header flow-card-header--compact">
              <div>
                <h2>消息设置</h2>
                <span>
                  {settings.data?.items?.length ? "可配置" : "接口暂不可用"}
                </span>
              </div>
            </div>
            {settings.data?.items?.length ? (
              <div className="quick-action-grid">
                {settings.data.items.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    disabled={!item.mutable || updateSetting.isPending}
                    onClick={() =>
                      updateSetting.mutate({
                        key: item.key,
                        enabled: !item.enabled,
                      })
                    }
                  >
                    {notificationSettingLabel(item.key, item.label)}：{item.enabled ? "开" : "关"}
                  </button>
                ))}
              </div>
            ) : (
              <div className="flow-side-empty">
                <EmptyState title="暂无数据" description="当前没有消息设置" />
              </div>
            )}
          </GlassCard>

          <GlassCard className="flow-side-card notification-actions-card">
            <div className="flow-card-header flow-card-header--compact">
              <div>
                <h2>快速处理</h2>
                <span>{summary.data?.unread ? `${summary.data.unread} 条未读` : "可用操作"}</span>
              </div>
            </div>
            <div className="quick-action-grid">
              <button
                type="button"
                disabled={markAll.isPending || clearRead.isPending}
                onClick={() => markAll.mutate()}
              >
                <CheckCheck size={16} />
                {markAll.isPending ? "处理中" : "全部标为已读"}
              </button>
              <button
                type="button"
                disabled={clearRead.isPending || markAll.isPending}
                onClick={() => clearRead.mutate()}
              >
                <Trash2 size={16} />
                {clearRead.isPending ? "清理中" : "清空已读"}
              </button>
              <button
                type="button"
                onClick={() => {
                  const email = settings.data?.items?.find((item) =>
                    item.key.includes("email")
                  );
                  if (email?.mutable) {
                    updateSetting.mutate({
                      key: email.key,
                      enabled: !email.enabled,
                    });
                  } else {
                    setMessage(
                      "邮件通知配置由系统统一管理，当前账号不可直接修改。"
                    );
                  }
                }}
              >
                <Mail size={16} />
                邮件通知
              </button>
            </div>
          </GlassCard>
        </aside>
      </section>

      {detailItem && (
        <div
          className="notification-detail-overlay"
          onClick={() => setDetailItem(null)}
        >
          <div
            className="notification-detail-modal glass-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="notification-detail-header">
              <h2>{detailItem.title || "通知详情"}</h2>
              <button
                type="button"
                className="notification-detail-close"
                onClick={() => setDetailItem(null)}
              >
                <X size={20} />
              </button>
            </div>
            <div className="notification-detail-body">
              <p className="notification-detail-content">
                {detailItem.content || "暂无内容"}
              </p>
              <div className="notification-detail-meta">
                {detailItem.notification_type && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">通知类型</span>
                    <span className="detail-meta-value">
                      <StatusBadge status={detailItem.notification_type} />
                    </span>
                  </div>
                )}
                {detailItem.channel && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">发送渠道</span>
                    <span className="detail-meta-value">{detailItem.channel}</span>
                  </div>
                )}
                <div className="detail-meta-item">
                  <span className="detail-meta-label">阅读状态</span>
                  <span className="detail-meta-value">
                    <StatusBadge
                      status={detailItem.read_status === "read" ? "read" : "unread"}
                    />
                  </span>
                </div>
                {detailItem.delivery_status && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">投递状态</span>
                    <span className="detail-meta-value">
                      <StatusBadge status={detailItem.delivery_status} />
                    </span>
                  </div>
                )}
                <div className="detail-meta-item">
                  <span className="detail-meta-label">发送时间</span>
                  <span className="detail-meta-value">
                    {formatDateTime(detailItem.sent_at || detailItem.created_at)}
                  </span>
                </div>
                {detailItem.read_at && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">阅读时间</span>
                    <span className="detail-meta-value">
                      {formatDateTime(detailItem.read_at)}
                    </span>
                  </div>
                )}
                {detailItem.related_entity_type && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">关联类型</span>
                    <span className="detail-meta-value">
                      {detailItem.related_entity_type}
                    </span>
                  </div>
                )}
                {detailItem.delivery_code && (
                  <div className="detail-meta-item">
                    <span className="detail-meta-label">投递编号</span>
                    <span className="detail-meta-value detail-meta-code">
                      {detailItem.delivery_code}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
