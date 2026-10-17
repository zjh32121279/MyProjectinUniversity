import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, BookOpenCheck, Clock, LayoutList, MapPin, RefreshCcw } from "lucide-react";
import { BookCover } from "@/components/common/BookCover";
import { EmptyState } from "@/components/common/EmptyState";
import { FlowFeedback } from "@/components/common/FlowFeedback";
import { GlassCard } from "@/components/common/GlassCard";
import { Pagination } from "@/components/common/Pagination";
import { StatCard } from "@/components/common/StatCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useBorrowList, useBorrowReminders, useBorrowSummary } from "@/hooks/useBorrowList";
import { borrowApi } from "@/services/borrowApi";
import type { BorrowRecord } from "@/types/borrow";
import { formatDate } from "@/utils/formatDate";
import { circulationTypeText } from "@/utils/statusText";

const statusCycle = ["", "active", "overdue", "returned"] as const;
const statusLabel: Record<string, string> = { "": "当前借阅", active: "借阅中", overdue: "已逾期", returned: "已归还" };

export function BorrowPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pageSize = 4;
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof statusCycle)[number]>("");
  const [sortAsc, setSortAsc] = useState(true);
  const summary = useBorrowSummary();
  const list = useBorrowList({ status: statusFilter || undefined, limit: pageSize, offset });
  const reminders = useBorrowReminders();
  const rules = useQuery({ queryKey: ["borrow-rules"], queryFn: borrowApi.getBorrowRules });
  const ruleData = rules.data as { items?: Array<{ circulation_type?: string; max_borrow_count?: number; borrow_days?: number; max_renewals?: number }> } | null | undefined;
  const renewMutation = useMutation({
    mutationFn: borrowApi.renewBorrow,
    onSuccess: async () => {
      setMessage("续借成功，到期日期已更新。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["borrow-list"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-reminders"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      ]);
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "续借服务暂不可用"),
  });
  const returnMutation = useMutation({
    mutationFn: borrowApi.returnBorrow,
    onSuccess: async (data) => {
      setMessage(`还书申请已提交，凭证码 ${data.voucher_code}，请到服务台交书并由馆员确认。`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["borrow-list"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["borrow-reminders"] }),
        queryClient.invalidateQueries({ queryKey: ["home-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      ]);
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "还书申请暂不可用"),
  });
  const items = [...(list.data?.items ?? [])].sort((a, b) => {
    const left = new Date(a.due_at || "9999-12-31").getTime();
    const right = new Date(b.due_at || "9999-12-31").getTime();
    return sortAsc ? left - right : right - left;
  });

  const cycleStatus = () => {
    const next = statusCycle[(statusCycle.indexOf(statusFilter) + 1) % statusCycle.length];
    setStatusFilter(next);
    setOffset(0);
  };
  const isCheckedOut = (item: BorrowRecord) => {
    const copyStatus = item.copy?.copy_status || item.copy?.status;
    return item.status === "active" || item.status === "overdue" || copyStatus === "borrowed";
  };

  const locationActionLabel = (item: BorrowRecord) => {
    if (item.status === "returned" || item.returned_at) return "已归还";
    if (isCheckedOut(item)) return "已取走";
    return "查看位置";
  };

  const showLocation = (item: BorrowRecord) => {
    const title = item.title || item.book?.title || "图书";
    const copyCode = item.copy_code || item.copy?.copy_code || "暂无副本号";
    if (item.status === "returned" || item.returned_at) {
      setMessage(`《${title}》已归还，当前借阅记录不再提供馆内定位。`);
      return;
    }
    if (isCheckedOut(item)) {
      setMessage(`《${title}》已取走，副本 ${copyCode} 当前不在馆内书架上。`);
      return;
    }

    const bookId = item.book?.id;
    const copyId = item.copy?.id;
    if (bookId || copyId) {
      const next = new URLSearchParams();
      if (title) next.set("query", title);
      if (bookId) next.set("book_id", String(bookId));
      if (copyId) next.set("copy_id", String(copyId));
      navigate(`/search?${next.toString()}`);
      return;
    }

    const location = item.location || "系统暂未返回馆藏架位，请联系馆员按副本号查找。";
    setMessage(`《${title}》位置：${location}；副本：${copyCode}`);
  };

  return (
    <main className="user-page user-flow-page borrow-page">
      <section className="page-title flow-title">
        <h1>我的借阅</h1>
        <p>查看当前借阅、到期提醒与续借状态。</p>
      </section>

      <section className="stat-grid flow-stat-grid">
        <StatCard icon={<BookOpenCheck size={26} />} label="当前借阅" value={summary.data?.current} unit="册" />
        <StatCard icon={<Clock size={26} />} label="即将到期" value={summary.data?.dueSoon} unit="册" tone="orange" />
        <StatCard icon={<AlertCircle size={26} />} label="已逾期" value={summary.data?.overdue} unit="册" tone="red" />
        <StatCard icon={<RefreshCcw size={26} />} label="可续借" value={summary.data?.renewable} unit="册" tone="green" />
      </section>

      <section className="flow-layout">
        <GlassCard className="records-card flow-records-card">
          <FlowFeedback message={message} />
          <div className="flow-card-header">
            <div>
              <h2>当前借阅</h2>
              <span>{list.isLoading ? "加载中" : items.length ? `${items.length} 条记录` : "暂无记录"}</span>
            </div>
            <div className="flow-toolbar" aria-label="借阅筛选工具栏">
              <button type="button" className={statusFilter ? "is-active" : ""} onClick={cycleStatus}>{statusLabel[statusFilter]}</button>
              <button type="button" className="is-active" onClick={() => setSortAsc((value) => !value)}>按到期日期{sortAsc ? "↑" : "↓"}</button>
              <button className="icon-only is-active" type="button" aria-label="列表视图"><LayoutList size={18} /></button>
            </div>
          </div>

          {items.length ? (
            <div className="record-list flow-list">
              {items.map((item) => (
                <article className="reader-record flow-record-row" key={item.loan_id}>
                  <BookCover compact src={item.cover_url || item.book?.cover_url} title={item.title || item.book?.title} />
                  <div className="flow-record-main">
                    <h3>{item.title || item.book?.title || "—"}</h3>
                    <p>{item.book?.author || "—"}</p>
                  </div>
                  <span>借阅日期<br /><strong>{formatDate(item.borrowed_at)}</strong></span>
                  <span>到期日期<br /><strong>{formatDate(item.due_at)}</strong></span>
                  <StatusBadge status={item.status} />
                  <div className="flow-actions">
                    {item.can_renew ? (
                      <button type="button" disabled={!item.loan_id || renewMutation.isPending} onClick={() => item.loan_id && renewMutation.mutate(item.loan_id)}>{renewMutation.isPending ? "续借中" : "续借"}</button>
                    ) : item.status === "active" || item.status === "overdue" ? (
                      <button type="button" disabled title={item.renew_blocked_reason || "当前记录不可续借"}>不可续借</button>
                    ) : null}
                    {item.status === "active" || item.status === "overdue" ? (
                      <button type="button" disabled={!item.loan_id || returnMutation.isPending} onClick={() => item.loan_id && returnMutation.mutate(item.loan_id)}>{returnMutation.isPending ? "提交中" : "申请还书"}</button>
                    ) : null}
                    <button type="button" onClick={() => showLocation(item)}><MapPin size={14} /> {locationActionLabel(item)}</button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="flow-empty-zone"><EmptyState title="暂无借阅记录" description={list.isError ? "数据暂不可用" : "当前账号没有可显示的借阅数据"} /></div>
          )}
          <Pagination total={list.data?.total} limit={list.data?.limit ?? pageSize} offset={list.data?.offset ?? offset} onPageChange={setOffset} />
        </GlassCard>

        <aside className="right-rail flow-right-rail">
          <GlassCard className="flow-side-card flow-timeline-card">
            <div className="flow-card-header flow-card-header--compact"><div><h2>到期提醒</h2><span>{reminders.data?.length ? `${reminders.data.length} 条提醒` : "暂无提醒"}</span></div></div>
            {reminders.data?.length ? (<div className="flow-timeline">{reminders.data.map((item) => (<article key={item.loan_id}><i /><div><strong>{item.title || item.book?.title || "—"}</strong><span>{formatDate(item.due_at)}</span></div></article>))}</div>) : (<div className="flow-side-empty"><EmptyState title="暂无借阅记录" /></div>)}
          </GlassCard>
          <GlassCard className="flow-side-card flow-rules-card">
            <div className="flow-card-header flow-card-header--compact"><div><h2>借阅规则</h2><span>{rules.data ? "已连接" : "暂无规则"}</span></div></div>
            {ruleData?.items?.length ? (
              <div className="flow-rule-list">
                {ruleData.items.map((item) => (
                  <article key={item.circulation_type || "rule"}>
                    <strong>{circulationTypeText(item.circulation_type)}</strong>
                    <span>最多 {item.max_borrow_count ?? "—"} 册</span>
                    <span>{item.borrow_days ?? "—"} 天</span>
                    <span>可续借 {item.max_renewals ?? "—"} 次</span>
                  </article>
                ))}
              </div>
            ) : (
              <div className="flow-side-empty"><EmptyState title="暂无数据" description={rules.isError ? "借阅规则服务暂不可用" : "当前没有借阅规则配置"} /></div>
            )}
          </GlassCard>
        </aside>
      </section>
    </main>
  );
}
