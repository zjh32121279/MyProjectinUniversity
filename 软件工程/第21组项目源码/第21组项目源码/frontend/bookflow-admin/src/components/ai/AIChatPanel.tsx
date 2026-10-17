import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiApi } from "@/api/ai";
import { AppIcon } from "@/components/icons/AppIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuthStore } from "@/stores/authStore";
import type { AnyRecord } from "@/types/api";
import { cn } from "@/utils/cn";
import { formatAIReason, formatErrorCode } from "@/utils/labels";
import aiAssistant from "@/assets/ai/home-ai-assistant.svg";

type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  meta?: AnyRecord;
  createdAt?: string;
};

type AIChatPanelProps = {
  engineConfigured?: boolean;
  engineStatus?: AnyRecord;
  onRefreshStatus?: () => void;
  fillParent?: boolean;
};

type ConversationItem = {
  conversation_id?: string;
  conversation_code?: string;
  title?: string;
  updated_at?: string;
  created_at?: string;
};

const quickPrompts = [
  { label: "查询馆藏", prompt: "帮我查一下馆里有多少本书名包含“”的书。" },
  { label: "查询读者", prompt: "帮我查一下读者编号为“”的借阅情况。" },
  { label: "逾期情况", prompt: "帮我统计当前逾期借阅，并按逾期天数分组。" },
  { label: "通知草拟", prompt: "请基于当前逾期记录生成一条提醒通知草稿。" },
  { label: "规则解释", prompt: "请解释当前借阅规则对热门书、普通书和冷门书的处理差异。" },
];

function formatTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function getConversationTitle(messages: ChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.role === "user")?.content.trim();
  if (!firstUserMessage) return "当前新聊天";
  return firstUserMessage.length > 18 ? `${firstUserMessage.slice(0, 18)}…` : firstUserMessage;
}

function getConversationId(item: ConversationItem) {
  return String(item.conversation_id ?? item.conversation_code ?? "");
}

function getConversationTitleFromItem(item: ConversationItem) {
  const title = String(item.title ?? "").trim();
  if (!title) return "BookFlow AI";
  return title.length > 18 ? `${title.slice(0, 18)}…` : title;
}

function PanelToggleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn("block", className)} fill="none">
      <rect x="4" y="5" width="16" height="14" rx="4" stroke="currentColor" strokeWidth="1.7" />
      <path d="M10 5.8v12.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function StatusPill({ connected }: { connected?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm font-bold",
        connected ? "border-[#d7f5e5] bg-[#f0fdf6] text-[#178c4a]" : "border-[#e5e9f3] bg-[#f8fafc] text-[#64748b]",
      )}
    >
      <span className={cn("h-2.5 w-2.5 rounded-full", connected ? "bg-[#18b66a]" : "bg-[#a7b0c3]")} />
      {connected ? "已连接" : "未连接"}
    </span>
  );
}

function getEngineFailureText(status?: AnyRecord) {
  const missing = Array.isArray(status?.missing_env) ? status?.missing_env.filter(Boolean).join("、") : "";
  if (missing) return `缺少配置项：${missing}`;
  const probe = status?.probe as AnyRecord | undefined;
  const reason = String(probe?.reason ?? status?.reason ?? "").trim();
  if (reason && reason !== "not_requested") return `连接检测失败：${formatAIReason(reason)}`;
  return "AI 引擎尚未连接，连接后即可进行馆藏查询、读者服务、通知生成等智能支持。";
}

export function AIChatPanel({ engineConfigured, engineStatus, onRefreshStatus, fillParent }: AIChatPanelProps) {
  const admin = useAuthStore((state) => state.admin);
  const queryClient = useQueryClient();
  const messageListRef = useRef<HTMLDivElement>(null);
  const [conversationId, setConversationId] = useState("");
  const [input, setInput] = useState("");
  const [searchText, setSearchText] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState("");
  const [renamingId, setRenamingId] = useState("");
  const [renameTitle, setRenameTitle] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);

  const conversations = useQuery({
    queryKey: ["ai", "conversations"],
    queryFn: () => aiApi.conversations({ limit: 50, offset: 0 }),
    enabled: !!engineConfigured,
  });

  const conversationItems = (conversations.data?.items ?? []) as ConversationItem[];
  const selectedConversation = conversationItems.find((item) => getConversationId(item) === conversationId);

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => aiApi.renameConversation(id, title),
    onSuccess: () => {
      setRenamingId("");
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (id === conversationId) { setConversationId(""); setMessages([]); }
      return aiApi.deleteConversation(id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
    },
  });

  const createConversation = useMutation({
    mutationFn: (title?: string) => aiApi.createConversation({ title: title || "BookFlow AI" }),
    onSuccess: (data) => {
      const nextId = String(data.conversation_id ?? data.conversation_code ?? "");
      if (nextId) setConversationId(nextId);
      setMessages([]);
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
    },
  });

  const messagesQuery = useQuery({
    queryKey: ["ai", "conversation-messages", conversationId],
    queryFn: () => aiApi.conversationMessages(conversationId, { limit: 100, offset: 0 }),
    enabled: !!engineConfigured && !!conversationId,
  });

  useEffect(() => {
    const remoteMessages = messagesQuery.data?.items;
    if (!remoteMessages) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages(
      remoteMessages.map((item) => {
        const role = String(item.role ?? "");
        return {
          role: role === "user" || role === "assistant" || role === "system" ? role : "assistant",
          content: String(item.content ?? ""),
          createdAt: String(item.created_at ?? ""),
        };
      }),
    );
  }, [messagesQuery.data]);

  const conversationTitle = useMemo(() => selectedConversation?.title || getConversationTitle(messages), [messages, selectedConversation?.title]);
  const filteredConversations = conversationItems.filter((item) => {
    const text = searchText.trim();
    return !text || getConversationTitleFromItem(item).includes(text);
  });

  const chat = useMutation({
    mutationFn: (text: string) => aiApi.chat({ conversation_id: conversationId, text }),
    onSuccess: (data) => {
      const reply = String(data.final_reply ?? data.reply ?? data.message ?? "");
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: reply || "AI 接口已返回，但未包含可展示的回复文本。",
          meta: data,
          createdAt: new Date().toISOString(),
        },
      ]);
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversations"] });
      void queryClient.invalidateQueries({ queryKey: ["ai", "conversation-messages", conversationId] });
    },
    onError: (error) => {
      setMessages((current) => [...current, { role: "system", content: formatErrorCode(error.message), createdAt: new Date().toISOString() }]);
    },
  });

  useEffect(() => {
    const node = messageListRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages.length, chat.isPending, conversationId]);

  function startNewChat() {
    if (!engineConfigured || createConversation.isPending) return;
    setInput("");
    createConversation.mutate("BookFlow AI");
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || !engineConfigured || !conversationId) return;
    setMessages((current) => [...current, { role: "user", content: text, createdAt: new Date().toISOString() }]);
    setInput("");
    chat.mutate(text);
  }

  const shellClassName = cn(
    "bf-card flex min-h-0 min-w-0 overflow-hidden rounded-[18px] bg-white",
    isFullscreen
      ? "fixed inset-5 z-50 h-[calc(100vh-40px)] shadow-[0_24px_70px_rgba(15,23,42,0.18)]"
      : fillParent ? "h-full" : "h-[calc(100vh-112px)]",
  );

  return (
    <div className={shellClassName}>
      {!isHistoryCollapsed ? (
        <aside className="flex min-h-0 w-[282px] shrink-0 flex-col border-r border-[#edf1f7] bg-[#fbfcff] transition-all duration-200">
          <>
            <div className="space-y-3 p-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-black text-[#7a86a1]">AI 聊天记录</span>
                <button
                  type="button"
                  onClick={() => setIsHistoryCollapsed(true)}
                  className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-[#d9e2f1] bg-white text-[#6b7280] shadow-none transition hover:border-[#cbd5e1] hover:bg-[#f8fbff]"
                  title="收起聊天记录"
                  aria-label="收起聊天记录"
                >
                  <PanelToggleIcon className="h-[20px] w-[20px]" />
                </button>
              </div>
              <button
                type="button"
                onClick={startNewChat}
                className="flex h-12 w-full items-center gap-3 rounded-xl border border-[#dce4f2] bg-white px-4 text-left text-[15px] font-bold text-[#17213c] shadow-[0_8px_18px_rgba(15,23,42,0.03)] transition hover:bg-[#f7faff]"
              >
                <AppIcon name="edit" size={19} className="text-[#4f46e5]" />
                新聊天
              </button>
              <label className="flex h-12 w-full items-center gap-3 rounded-xl border border-[#dce4f2] bg-white px-4 text-[15px] font-semibold text-[#71809c] shadow-[0_8px_18px_rgba(15,23,42,0.03)] focus-within:border-[#9eb8ff] focus-within:shadow-[0_0_0_4px_rgba(37,99,235,0.08)]">
                <AppIcon name="search" size={19} className="text-[#4f46e5]" />
                <input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[#7d8ba5]"
                  placeholder="搜索聊天"
                />
              </label>
            </div>

            <div className="min-h-0 flex-1 overscroll-contain overflow-y-auto px-4 pb-4 bf-scrollbar">
              {filteredConversations.length ? (
                <>
                  <div className="mb-3 mt-4 text-sm font-black text-[#7a86a1]">今天</div>
                  <div className="space-y-2">
                    {filteredConversations.map((item) => {
                      const id = getConversationId(item);
                      const title = getConversationTitleFromItem(item);
                      const isMenuOpen = menuOpenId === id;
                      const isRenaming = renamingId === id;
                      return (
                        <div key={id} className={cn("group relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-[#ece7ff]", id === conversationId ? "bg-[#f0ecff]" : "bg-white")}>
                          <button
                            type="button"
                            className="flex min-w-0 flex-1 items-center gap-3 text-left"
                            onClick={() => {
                              if (!isRenaming) { setConversationId(id); setMessages([]); }
                            }}
                          >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-[#5b4bf2] shadow-sm">
                              <AppIcon name="document" size={15} />
                            </span>
                            <span className="min-w-0 flex-1">
                              {isRenaming ? (
                                <input
                                  className="w-full rounded-lg border border-[#d9e2f1] bg-white px-2 py-1 text-sm font-bold text-[#263452] outline-none focus:border-[#4f46e5]"
                                  value={renameTitle}
                                  onChange={(e) => setRenameTitle(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") renameMutation.mutate({ id, title: renameTitle });
                                    if (e.key === "Escape") setRenamingId("");
                                  }}
                                  onBlur={() => { if (!renameMutation.isPending) setRenamingId(""); }}
                                  autoFocus
                                  onClick={(e) => e.stopPropagation()}
                                />
                              ) : (
                                <>
                                  <span className="block truncate text-sm font-black text-[#263452]">{title}</span>
                                  <span className="mt-1 block text-xs font-semibold text-[#8792aa]">{formatTime(item.updated_at || item.created_at)}</span>
                                </>
                              )}
                            </span>
                          </button>
                          <button
                            type="button"
                            className="shrink-0 rounded-lg p-1 text-[#8792aa] opacity-0 transition hover:bg-[#e8e3f7] hover:text-[#4f46e5] group-hover:opacity-100"
                            onClick={(e) => { e.stopPropagation(); setMenuOpenId(isMenuOpen ? "" : id); }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="8" cy="3" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="8" cy="13" r="1.5"/></svg>
                          </button>
                          {isMenuOpen ? (
                            <div ref={menuRef} className="absolute right-2 top-full z-30 mt-1 w-32 rounded-xl border border-[#e7edf7] bg-white py-1 shadow-[0_16px_40px_rgba(15,23,42,0.12)]">
                              <button
                                type="button"
                                className="block w-full px-4 py-2 text-left text-[13px] font-bold text-[#17213c] hover:bg-[#f8fbff]"
                                onClick={() => { setMenuOpenId(""); setRenamingId(id); setRenameTitle(title); }}
                              >
                                重命名
                              </button>
                              <button
                                type="button"
                                className="block w-full px-4 py-2 text-left text-[13px] font-bold text-[#dc2626] hover:bg-[#fef2f2]"
                                onClick={() => { setMenuOpenId(""); setDeleteConfirmId(id); }}
                              >
                                删除
                              </button>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : null}
            </div>
          </>
        </aside>
      ) : null}

      <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#fbfcff]">
        <header className="flex h-[78px] shrink-0 items-center justify-between border-b border-[#edf1f7] bg-[#fbfcff] px-7">
          <div className="flex min-w-0 items-center gap-4">
            {isHistoryCollapsed ? (
              <button
                type="button"
                onClick={() => setIsHistoryCollapsed(false)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] border border-[#d9e2f1] bg-white text-[#6b7280] shadow-none transition hover:border-[#cbd5e1] hover:bg-[#f8fbff]"
                title="展开聊天记录"
                aria-label="展开聊天记录"
              >
                <PanelToggleIcon className="h-[21px] w-[21px]" />
              </button>
            ) : null}
            <img src={aiAssistant} alt="BookFlow AI" className="h-11 w-11 shrink-0 rounded-full object-contain shadow-[0_10px_24px_rgba(91,75,242,0.14)]" />
            <div className="min-w-0">
              <div className="flex items-center gap-3" title={conversationTitle}>
                <h2 className="truncate text-[19px] font-black text-[#4f46e5]">BookFlow AI</h2>
                <StatusPill connected={engineConfigured} />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsFullscreen((value) => !value)}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#dce4f2] bg-white text-[#52617e] transition hover:bg-[#f7faff]"
              title={isFullscreen ? "退出全屏" : "全屏"}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M1 6V1h5M14 1h5v5M19 14v5h-5M6 19H1v-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button type="button" className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#dce4f2] bg-white text-[#52617e] transition hover:bg-[#f7faff]" title="更多操作">
              <span className="text-xl leading-none">…</span>
            </button>
          </div>
        </header>

        <div ref={messageListRef} className="min-h-0 flex-1 overscroll-contain overflow-y-auto bg-[#fbfcff] px-7 py-6 bf-scrollbar">
          {!conversationId ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center text-center">
              <img src={aiAssistant} alt="BookFlow AI" className="mb-6 h-24 w-24 rounded-full object-contain shadow-[0_18px_46px_rgba(91,75,242,0.12)]" />
              <h3 className="text-[26px] font-black text-[#101a35]">
                {engineConfigured ? "今天在忙什么？" : "你好，我是 BookFlow AI 助手"}
              </h3>
              <p className="mt-4 max-w-[620px] text-[15px] font-semibold leading-7 text-[#65728d]">
                {engineConfigured
                  ? "点击左侧「新聊天」开始对话，或选择历史记录继续。"
                  : getEngineFailureText(engineStatus)}
              </p>
              {!engineConfigured ? (
                <ActionButton type="button" className="mt-7" variant="purple" size="lg" icon="refresh" onClick={onRefreshStatus}>
                  刷新连接状态
                </ActionButton>
              ) : null}
            </div>
          ) : !messages.length ? (
            <div className="flex h-full min-h-[420px] flex-col items-center justify-center text-center">
              <img src={aiAssistant} alt="BookFlow AI" className="mb-6 h-24 w-24 rounded-full object-contain shadow-[0_18px_46px_rgba(91,75,242,0.12)]" />
              <h3 className="text-[26px] font-black text-[#101a35]">今天要处理什么馆务？</h3>
              <p className="mt-4 max-w-[620px] text-[15px] font-semibold leading-7 text-[#65728d]">AI 引擎已连接，可根据馆藏、借阅、预约、读者和任务数据协助处理馆务。</p>
            </div>
          ) : null}

          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={cn("mb-6 flex gap-3", message.role === "user" && "justify-end")}>
              {message.role !== "user" ? <img src={aiAssistant} alt="BookFlow AI" className="h-10 w-10 shrink-0 rounded-full object-contain" /> : null}
              <div className={cn("min-w-0 max-w-[72%]", message.role === "user" && "flex flex-col items-end")}>
                <div className={cn("mb-2 flex items-center gap-2 text-xs font-bold text-[#7b86a2]", message.role === "user" && "justify-end")}>
                  <span>{message.role === "user" ? admin?.name || admin?.admin_code || "管理员" : message.role === "system" ? "系统提示" : "BookFlow AI"}</span>
                  <span>{formatTime(message.createdAt)}</span>
                </div>
                <div
                  className={cn(
                    "rounded-2xl px-5 py-4 text-[15px] leading-7 shadow-sm",
                    message.role === "user"
                      ? "bg-[#ece9ff] text-[#111827]"
                      : message.role === "system"
                        ? "bg-[var(--bf-danger-soft)] text-[var(--bf-danger)]"
                        : "border border-[var(--bf-border-soft)] bg-white text-[#17213c]",
                  )}
                >
                  {message.content}
                </div>
              </div>
            </div>
          ))}
          {chat.isPending ? (
            <div className="mb-6 flex items-center gap-3 text-sm font-semibold text-[#69758f]">
              <img src={aiAssistant} alt="BookFlow AI" className="h-10 w-10 rounded-full object-contain" />
              <span className="rounded-2xl border border-[#e6ebf5] bg-white px-4 py-3 shadow-sm">BookFlow AI 正在处理馆务请求…</span>
            </div>
          ) : null}
        </div>

        {conversationId ? (
        <form className="shrink-0 border-t border-[var(--bf-border-soft)] bg-[#fbfcff] px-7 py-4" onSubmit={onSubmit}>
          <div className="mb-3 flex flex-wrap gap-3">
            {quickPrompts.map((item) => (
              <button
                key={item.label}
                type="button"
                className={cn(
                  "inline-flex h-10 items-center gap-2 rounded-xl border border-[var(--bf-border-soft)] bg-[#fbfcff] px-4 text-sm font-bold text-[#1b2848] transition hover:bg-[#f7faff]",
                  !engineConfigured && "cursor-not-allowed opacity-55",
                )}
                onClick={() => engineConfigured && setInput(item.prompt)}
                disabled={!engineConfigured}
              >
                <AppIcon name={item.label === "查询馆藏" ? "catalog" : item.label === "查询读者" ? "readers" : item.label === "通知草拟" ? "notifications" : item.label === "规则解释" ? "settings" : "data"} size={16} className="text-[#4f46e5]" />
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex min-w-0 gap-3">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              className="bf-control h-12 min-w-0 flex-1 px-4 text-sm"
              placeholder={engineConfigured ? (conversationId ? "输入馆务问题或指令…" : "正在创建聊天记录…") : "AI 引擎未连接，请先连接后再输入指令"}
              disabled={!engineConfigured || !conversationId}
            />
            <ActionButton type="submit" size="lg" icon="send" disabled={chat.isPending || !engineConfigured || !conversationId || !input.trim()}>
              发送
            </ActionButton>
          </div>
          <div className="mt-3 text-center text-xs font-semibold text-[var(--bf-text-secondary)]">内容由 AI 生成，仅供参考，请核实后使用</div>
        </form>
        ) : null}
      </section>

      <ConfirmDialog
        open={!!deleteConfirmId}
        onOpenChange={(open) => { if (!open) setDeleteConfirmId(""); }}
        title="删除聊天记录"
        description="确定要删除这条聊天记录吗？所有消息将被永久移除。"
        onConfirm={() => { deleteMutation.mutate(deleteConfirmId); setDeleteConfirmId(""); }}
      />
    </div>
  );
}
