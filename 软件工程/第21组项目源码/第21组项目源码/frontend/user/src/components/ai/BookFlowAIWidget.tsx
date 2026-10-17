import { useEffect, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { BookOpenCheck, CalendarPlus, Send, Search, X } from "lucide-react";
import assistantAsset from "@/assets/home-ai-assistant.svg";
import { aiApi, type ReaderAIAction } from "@/services/aiApi";
import { getReaderSession } from "@/services/readerApi";
import { formatDataFieldLabel, formatDataFieldValue, formatRequestedAction, formatServiceType, formatStatus } from "@common/utils/labels";

type BookFlowAIWidgetProps = {
  expanded: boolean;
  onToggle: () => void;
  onCollapse?: () => void;
  dragging?: boolean;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  actions?: ReaderAIAction[];
};

const DEFAULT_SUGGESTIONS = [
  "最近有什么热门新书？",
  "我借的书快到期了吗？",
  "帮我找一本关于历史的书",
  "怎么预约已经借出的书？",
];

const SUGGESTION_ICONS = [Search, BookOpenCheck, CalendarPlus, Search];

function ActionResultCard({ action }: { action: ReaderAIAction }) {
  const fields = action.fields ?? [];
  const title = action.title || `${formatServiceType(action.request_type)} · ${formatStatus(action.status)}`;
  return (
    <div className="ai-widget__action-card">
      <strong>{formatRequestedAction(title)}</strong>
      {action.summary ? <span>{action.summary}</span> : null}
      {fields.length ? (
        <dl>
          {fields.map((field) => (
            <div key={`${field.label}-${field.value}`}>
              <dt>{formatDataFieldLabel(field.label)}</dt>
              <dd>{formatDataFieldValue(field.label, field.value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

export function BookFlowAIWidget({ expanded, onToggle, onCollapse, dragging = false }: BookFlowAIWidgetProps) {
  const hasReaderSession = Boolean(getReaderSession()?.reader_code);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!expanded || !hasReaderSession) {
      setSuggestions([]);
      return;
    }
    aiApi.getSuggestions().then((list) => setSuggestions(list.length ? list : DEFAULT_SUGGESTIONS)).catch(() => setSuggestions(DEFAULT_SUGGESTIONS));
  }, [expanded, hasReaderSession]);

  async function sendMessage(text: string) {
    const content = text.trim();
    if (!content) return;
    if (!hasReaderSession) {
      setMessage("登录后可使用 BookFlow AI");
      return;
    }
    setLoading(true);
    setMessage("");
    const history = messages.map((item) => ({ role: item.role, content: item.content }));
    setMessages((current) => [...current, { role: "user", content }]);
    try {
      const data = await aiApi.chat(content, history);
      setMessages((current) => [...current, { role: "assistant", content: data.answer, actions: data.actions ?? [] }]);
      setInput("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "BookFlow AI 服务暂不可用");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  const dialog = expanded
    ? createPortal(
        <div
          className="ai-widget__dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="bookflow-ai-title"
          onKeyDown={(event) => {
            if (event.key === "Escape") onCollapse?.();
          }}
          onPointerDown={(event) => event.stopPropagation()}
          onPointerMove={(event) => event.stopPropagation()}
          onPointerUp={(event) => event.stopPropagation()}
        >
          <div className="ai-widget__backdrop" onClick={onCollapse} />
          <div className="ai-widget__panel">
            <header>
              <img className="ai-widget__header-avatar" src={assistantAsset} alt="" />
              <div>
                <strong id="bookflow-ai-title">BookFlow AI</strong>
                <span>你的私人图书馆助手</span>
              </div>
              <button type="button" onClick={onCollapse} aria-label="收起 BookFlow AI">
                <X size={20} />
              </button>
            </header>
            <div className="ai-widget__content">
              {hasReaderSession ? null : (
                <div className="ai-widget__login-hint">
                  <img src={assistantAsset} alt="" />
                  <p>登录后即可使用 AI 助手查找图书、管理借阅</p>
                </div>
              )}
              <div className="ai-widget__body">
                {message ? <p className="ai-widget__error">{message}</p> : null}
                {messages.length ? (
                  <div className="ai-widget__messages">
                    {messages.map((item, index) => (
                      <div key={`${item.role}-${index}`} className={`ai-widget__message ai-widget__message--${item.role}`}>
                        {item.role === "assistant" ? <img className="ai-widget__msg-avatar" src={assistantAsset} alt="" /> : null}
                        <div className="ai-widget__msg-body">
                          <p>{item.content}</p>
                          {item.actions?.map((action, actionIndex) => <ActionResultCard key={`${action.title}-${actionIndex}`} action={action} />)}
                        </div>
                      </div>
                    ))}
                    {loading ? (
                      <div className="ai-widget__message ai-widget__message--assistant">
                        <img className="ai-widget__msg-avatar" src={assistantAsset} alt="" />
                        <div className="ai-widget__msg-body">
                          <div className="ai-widget__typing">
                            <span /><span /><span />
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="ai-widget__welcome">
                    <img src={assistantAsset} alt="" />
                    <strong>你好，我能帮你做什么？</strong>
                    <em>找书、查借阅、预约排队、了解馆藏，尽管问我</em>
                  </div>
                )}
                {!messages.length && suggestions.length ? (
                  <div className="ai-widget__suggestions">
                    {suggestions.map((item, index) => {
                      const Icon = SUGGESTION_ICONS[index % SUGGESTION_ICONS.length];
                      return (
                        <button key={item} type="button" onClick={() => sendMessage(item)} disabled={loading}>
                          <Icon size={14} />
                          <span>{item}</span>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            </div>
            <form onSubmit={handleSubmit}>
              <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入你的问题…" disabled={loading} />
              <button type="submit" disabled={loading || !input.trim()} aria-label="发送">
                <Send size={17} />
              </button>
            </form>
          </div>
        </div>,
        document.body,
      )
    : null;

  return (
    <div className={dragging ? "ai-widget ai-widget--dragging" : "ai-widget"}>
      {dialog}
      <button className="ai-widget__robot" type="button" onClick={onToggle} aria-label="打开 BookFlow AI">
        <span className="ai-widget__tip">问我找书、续借、预约都可以</span>
        <img src={assistantAsset} alt="" />
        <strong>BookFlow AI</strong>
      </button>
    </div>
  );
}
