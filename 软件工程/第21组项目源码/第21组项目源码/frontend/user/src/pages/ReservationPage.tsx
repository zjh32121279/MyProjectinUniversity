import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, BookMarked, CalendarX, Clock, History, LayoutList, MapPin, Ticket } from "lucide-react";
import { BookCover } from "@/components/common/BookCover";
import { EmptyState } from "@/components/common/EmptyState";
import { FlowFeedback } from "@/components/common/FlowFeedback";
import { GlassCard } from "@/components/common/GlassCard";
import { Pagination } from "@/components/common/Pagination";
import { StatCard } from "@/components/common/StatCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { usePickupReminders, useReservationList, useReservationSummary } from "@/hooks/useReservationList";
import { reservationApi } from "@/services/reservationApi";
import type { ReservationRecord } from "@/types/reservation";
import { formatDate } from "@/utils/formatDate";
import { circulationTypeText } from "@/utils/statusText";

const statusCycle = ["", "waiting", "ready_for_pickup", "fulfilled", "cancelled", "expired"] as const;
const statusLabel: Record<string, string> = { "": "全部状态", waiting: "排队中", ready_for_pickup: "待取书", fulfilled: "已完成", cancelled: "已取消", expired: "已失效" };

export function ReservationPage() {
  const queryClient = useQueryClient();
  const pageSize = 8;
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof statusCycle)[number]>("");
  const [sortAsc, setSortAsc] = useState(false);
  const summary = useReservationSummary();
  const list = useReservationList({ status: statusFilter || undefined, limit: pageSize, offset });
  const reminders = usePickupReminders();
  const rules = useQuery({ queryKey: ["reservation-rules"], queryFn: reservationApi.getReservationRules });
  const ruleData = rules.data as { reservation_limit?: number; hold_days?: number; items?: Array<{ circulation_type?: string; reservation_limit?: number; borrow_days?: number }> } | null | undefined;
  const cancelMutation = useMutation({
    mutationFn: reservationApi.cancelReservation,
    onSuccess: async () => {
      setMessage("预约已取消，相关副本和预约队列会同步刷新。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["reservation-list"] }),
        queryClient.invalidateQueries({ queryKey: ["reservation-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["pickup-reminders"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["book-search"] }),
      ]);
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "取消预约服务暂不可用"),
  });
  const pickupCodeMutation = useMutation({
    mutationFn: reservationApi.getPickupCode,
    onSuccess: (data) => {
      const code = typeof data === "object" && data ? JSON.stringify(data) : String(data ?? "暂无取书码");
      setMessage(`取书码信息：${code}`);
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "取书码暂不可用"),
  });
  const items = [...(list.data?.items ?? [])].sort((a, b) => {
    const left = new Date(a.created_at || "1970-01-01").getTime();
    const right = new Date(b.created_at || "1970-01-01").getTime();
    return sortAsc ? left - right : right - left;
  });

  const cycleStatus = () => {
    const next = statusCycle[(statusCycle.indexOf(statusFilter) + 1) % statusCycle.length];
    setStatusFilter(next);
    setOffset(0);
  };
  const showLocation = (item: ReservationRecord) => {
    const copyCode = item.copy?.copy_code || "待系统分配副本";
    const location = (item as ReservationRecord & { location?: string }).location || (item.status === "ready_for_pickup" ? "预约保留区 / 服务台" : "排队中，暂未分配取书位置");
    setMessage(`《${item.book?.title || "图书"}》位置：${location}；副本：${copyCode}`);
  };

  return (
    <main className="user-page user-flow-page reservation-page">
      <section className="page-title flow-title">
        <h1>我的预约</h1>
        <p>查看排队进度、待取图书与预约记录。</p>
      </section>

      <section className="stat-grid flow-stat-grid">
        <StatCard icon={<Clock size={26} />} label="预约中" value={summary.data?.active} unit="本" />
        <StatCard icon={<BookMarked size={26} />} label="待取书" value={summary.data?.ready} unit="本" tone="orange" />
        <StatCard icon={<AlertCircle size={26} />} label="即将失效" value={summary.data?.expiring} unit="本" tone="red" />
        <StatCard icon={<History size={26} />} label="历史预约" value={summary.data?.history} unit="本" tone="green" />
      </section>

      <section className="flow-layout">
        <GlassCard className="records-card flow-records-card">
          <FlowFeedback message={message} />
          <div className="flow-card-header">
            <div><h2>当前预约</h2><span>{list.isLoading ? "加载中" : items.length ? `${items.length} 条记录` : "暂无记录"}</span></div>
            <div className="flow-toolbar" aria-label="预约筛选工具栏">
              <button type="button" className={statusFilter ? "is-active" : ""} onClick={cycleStatus}>{statusLabel[statusFilter]}</button>
              <button type="button" className="is-active" onClick={() => setSortAsc((value) => !value)}>按预约时间{sortAsc ? "↑" : "↓"}</button>
              <button className="icon-only is-active" type="button" aria-label="列表视图"><LayoutList size={18} /></button>
            </div>
          </div>

          {items.length ? (
            <div className="record-list flow-list">
              {items.map((item) => (
                <article className="reader-record flow-record-row" key={item.reservation_id}>
                  <BookCover compact title={item.book?.title} />
                  <div className="flow-record-main"><h3>{item.book?.title || "—"}</h3><p>{item.book?.author || "—"}</p></div>
                  <span>预约日期<br /><strong>{formatDate(item.created_at)}</strong></span>
                  <span>取书截止<br /><strong>{formatDate(item.reserved_until)}</strong></span>
                  <StatusBadge status={item.status} />
                  <div className="flow-actions">
                    <button type="button" disabled={!item.reservation_id || pickupCodeMutation.isPending} onClick={() => item.reservation_id && (item.pickup_code_available || item.status === "ready_for_pickup" ? pickupCodeMutation.mutate(item.reservation_id) : setMessage("该预约仍在排队中，到书后系统会生成取书码。"))}><Ticket size={14} /> {pickupCodeMutation.isPending ? "读取中" : "取书码"}</button>
                    <button type="button" onClick={() => showLocation(item)}><MapPin size={14} /> 查看位置</button>
                    <button type="button" disabled={!item.reservation_id || cancelMutation.isPending || item.status === "fulfilled" || item.status === "cancelled"} onClick={() => item.reservation_id && cancelMutation.mutate(item.reservation_id)}><CalendarX size={14} /> {cancelMutation.isPending ? "取消中" : "取消预约"}</button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="flow-empty-zone"><EmptyState title="暂无预约记录" description={list.isError ? "数据暂不可用" : "当前账号没有可显示的预约数据"} /></div>
          )}
          <Pagination total={list.data?.total} limit={list.data?.limit ?? pageSize} offset={list.data?.offset ?? offset} onPageChange={setOffset} />
        </GlassCard>

        <aside className="right-rail flow-right-rail">
          <GlassCard className="flow-side-card flow-timeline-card">
            <div className="flow-card-header flow-card-header--compact"><div><h2>待取提醒</h2><span>{reminders.data?.length ? `${reminders.data.length} 条提醒` : "暂无提醒"}</span></div></div>
            {reminders.data?.length ? (<div className="flow-timeline">{reminders.data.map((item) => (<article key={item.reservation_id}><i /><div><strong>{item.book?.title || "—"}</strong><span>{formatDate(item.reserved_until)}</span></div></article>))}</div>) : (<div className="flow-side-empty"><EmptyState title="暂无预约记录" /></div>)}
          </GlassCard>
          <GlassCard className="flow-side-card flow-rules-card">
            <div className="flow-card-header flow-card-header--compact"><div><h2>预约规则</h2><span>{rules.data ? "已连接" : "暂无规则"}</span></div></div>
            {ruleData ? (
              <div className="flow-rule-list">
                <article>
                  <strong>预约总规则</strong>
                  <span>最多 {ruleData.reservation_limit ?? "—"} 本</span>
                  <span>到书保留 {ruleData.hold_days ?? "—"} 天</span>
                </article>
                {(ruleData.items ?? []).map((item) => (
                  <article key={item.circulation_type || "rule"}>
                    <strong>{circulationTypeText(item.circulation_type)}</strong>
                    <span>上限 {item.reservation_limit ?? ruleData.reservation_limit ?? "—"} 本</span>
                    <span>借期 {item.borrow_days ?? "—"} 天</span>
                  </article>
                ))}
              </div>
            ) : (
              <div className="flow-side-empty"><EmptyState title="暂无数据" description={rules.isError ? "预约规则服务暂不可用" : "当前没有预约规则配置"} /></div>
            )}
          </GlassCard>
        </aside>
      </section>
    </main>
  );
}
