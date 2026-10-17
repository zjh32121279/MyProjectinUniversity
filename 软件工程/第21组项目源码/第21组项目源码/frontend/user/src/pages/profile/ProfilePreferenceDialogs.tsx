import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Clock, X } from "lucide-react";
import { ReaderBookDetailDialog } from "@/components/books/ReaderBookDetail";
import { bookApi } from "@/services/bookApi";
import { readerApi } from "@/services/readerApi";
import type { BookItem, CategoryOption } from "@/types/book";
import type { BorrowHistoryItem } from "@/types/user";

/* ===== 分类选择弹窗 ===== */
export function CategorySelectDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const categories = useQuery({ queryKey: ["category-options"], queryFn: bookApi.getCategoryOptions });
  const prefs = useQuery({ queryKey: ["reader-preferences"], queryFn: readerApi.getPreferences });
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>(prefs.data?.favorite_category_codes ?? []);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (prefs.data?.favorite_category_codes) setSelected(prefs.data.favorite_category_codes);
  }, [prefs.data?.favorite_category_codes]);

  function toggle(code: string) {
    setSelected((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  async function save() {
    setSaving(true);
    try {
      await readerApi.updatePreferences({ favorite_category_codes: selected });
      queryClient.invalidateQueries({ queryKey: ["reader-preferences"] });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="profile-detail-dialog" role="dialog" aria-modal="true" aria-label="选择偏好分类">
      <div className="profile-detail-dialog__backdrop" onClick={onClose} />
      <div className="profile-detail-dialog__panel" style={{ maxWidth: 520 }}>
        <button className="profile-detail-dialog__close" type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        <h3 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 900 }}>选择感兴趣的分类</h3>
        <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: 14 }}>勾选后首页"为你推荐"将优先展示这些分类的图书</p>
        <div style={{ maxHeight: 360, overflowY: "auto", display: "grid", gap: 6 }}>
          {(categories.data ?? []).map((cat: CategoryOption) => (
            <label key={cat.code ?? cat.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 10, cursor: "pointer", background: selected.includes(cat.code ?? "") ? "rgba(49,91,255,0.06)" : "transparent", border: selected.includes(cat.code ?? "") ? "1px solid rgba(49,91,255,0.25)" : "1px solid transparent" }}>
              <input type="checkbox" checked={selected.includes(cat.code ?? "")} onChange={() => toggle(cat.code ?? "")} style={{ accentColor: "#315bff" }} />
              <span style={{ fontWeight: 700, fontSize: 14 }}>{cat.name}</span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, justifyContent: "flex-end" }}>
          <button type="button" onClick={onClose} style={{ border: "1px solid #e2e8f0", borderRadius: 12, background: "#fff", padding: "10px 22px", fontWeight: 800, cursor: "pointer" }}>取消</button>
          <button type="button" onClick={save} disabled={saving} style={{ border: 0, borderRadius: 12, background: "linear-gradient(135deg,#315bff,#2563eb)", color: "#fff", padding: "10px 22px", fontWeight: 800, cursor: "pointer" }}>{saving ? "保存中" : "保存"}</button>
        </div>
      </div>
    </div>
  );
}

/* ===== 推荐策略选择弹窗 ===== */
export function RecommendationSelectDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const prefs = useQuery({ queryKey: ["reader-preferences"], queryFn: readerApi.getPreferences });
  const queryClient = useQueryClient();
  const [source, setSource] = useState(prefs.data?.recommendation_source ?? "both");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (prefs.data?.recommendation_source) setSource(prefs.data.recommendation_source);
  }, [prefs.data?.recommendation_source]);

  async function save() {
    setSaving(true);
    try {
      await readerApi.updatePreferences({ recommendation_source: source });
      queryClient.invalidateQueries({ queryKey: ["reader-preferences"] });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  const options: { value: typeof source; label: string; desc: string }[] = [
    { value: "popular", label: "热门馆藏", desc: "推荐当前借阅量最高的热门图书" },
    { value: "preference", label: "偏好分类", desc: "仅推荐您所选偏好分类中的图书" },
    { value: "both", label: "两者都有", desc: "混合推荐热门图书和偏好分类图书" },
  ];

  return (
    <div className="profile-detail-dialog" role="dialog" aria-modal="true" aria-label="选择推荐策略">
      <div className="profile-detail-dialog__backdrop" onClick={onClose} />
      <div className="profile-detail-dialog__panel" style={{ maxWidth: 480 }}>
        <button className="profile-detail-dialog__close" type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
        <h3 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 900 }}>推荐策略</h3>
        <p style={{ margin: "0 0 16px", color: "#64748b", fontSize: 14 }}>选择首页"为你推荐"的图书来源</p>
        <div style={{ display: "grid", gap: 8 }}>
          {options.map((opt) => (
            <label key={opt.value} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", borderRadius: 12, cursor: "pointer", background: source === opt.value ? "rgba(49,91,255,0.06)" : "transparent", border: source === opt.value ? "1px solid rgba(49,91,255,0.3)" : "1px solid rgba(148,163,184,0.18)" }}>
              <input type="radio" name="rec_source" value={opt.value} checked={source === opt.value} onChange={() => setSource(opt.value)} style={{ accentColor: "#315bff", marginTop: 2 }} />
              <div>
                <strong style={{ display: "block", fontSize: 14, fontWeight: 800 }}>{opt.label}</strong>
                <span style={{ fontSize: 12, color: "#64748b" }}>{opt.desc}</span>
              </div>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 18, justifyContent: "flex-end" }}>
          <button type="button" onClick={onClose} style={{ border: "1px solid #e2e8f0", borderRadius: 12, background: "#fff", padding: "10px 22px", fontWeight: 800, cursor: "pointer" }}>取消</button>
          <button type="button" onClick={save} disabled={saving} style={{ border: 0, borderRadius: 12, background: "linear-gradient(135deg,#315bff,#2563eb)", color: "#fff", padding: "10px 22px", fontWeight: 800, cursor: "pointer" }}>{saving ? "保存中" : "保存"}</button>
        </div>
      </div>
    </div>
  );
}

/* ===== 借阅历史时间线弹窗 ===== */
export function BorrowHistoryDialog({ onClose }: { onClose: () => void }) {
  const history = useQuery({ queryKey: ["borrow-history"], queryFn: () => readerApi.getBorrowHistory(100) });
  const [detailBook, setDetailBook] = useState<BookItem | null>(null);

  const items: BorrowHistoryItem[] = history.data ?? [];

  return (
    <>
      <div className="profile-detail-dialog" role="dialog" aria-modal="true" aria-label="借阅历史">
        <div className="profile-detail-dialog__backdrop" onClick={onClose} />
        <div className="profile-detail-dialog__panel" style={{ maxWidth: 680, maxHeight: "80vh", overflowY: "auto" }}>
          <button className="profile-detail-dialog__close" type="button" onClick={onClose} aria-label="关闭"><X size={20} /></button>
          <h3 style={{ margin: "0 0 4px", fontSize: 22, fontWeight: 900 }}>借阅历史</h3>
          <p style={{ margin: "0 0 20px", color: "#64748b", fontSize: 14 }}>共 {items.length} 条借阅记录</p>

          {items.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>
              <BookOpen size={48} style={{ opacity: 0.3 }} />
              <p>暂无借阅记录</p>
            </div>
          ) : (
            <div className="borrow-timeline">
              {items.map((item) => (
                <div key={item.loan_id} className={`borrow-timeline__item ${item.status === "returned" ? "is-returned" : "is-active"}`}>
                  <div className="borrow-timeline__node">
                    {item.status === "returned" ? <BookOpen size={16} /> : <Clock size={16} />}
                  </div>
                  <div className="borrow-timeline__content" style={{ cursor: "pointer" }} onClick={() => setDetailBook({ id: item.book_id, title: item.title, author: item.author, cover_url: item.cover_url })}>
                    {item.cover_url ? (
                      <img src={item.cover_url} alt={item.title} className="borrow-timeline__cover" />
                    ) : (
                      <div className="borrow-timeline__cover borrow-timeline__cover--placeholder"><BookOpen size={22} /></div>
                    )}
                    <div className="borrow-timeline__info">
                      <strong>{item.title}</strong>
                      <span>{item.author || "—"}</span>
                      <div className="borrow-timeline__dates">
                        <span>借于 {item.borrowed_at?.slice(0, 10) || "—"}</span>
                        {item.returned_at ? <span>还于 {item.returned_at.slice(0, 10)}</span> : <span style={{ color: "#f59e0b" }}>借阅中</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ReaderBookDetailDialog
        bookId={detailBook?.id}
        fallbackBook={detailBook}
        open={Boolean(detailBook)}
        onClose={() => setDetailBook(null)}
      />
    </>
  );
}
