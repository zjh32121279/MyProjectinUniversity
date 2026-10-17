import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { catalogApi } from "@/api/catalog";
import { AppIcon } from "@/components/icons/AppIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { FormDialog } from "@/components/ui/FormDialog";
import type { AnyRecord } from "@/types/api";

type CategoryManagerTab = "categories" | "subcategories";
type SubItem = { code: string; name: string };

const fieldClass = () =>
  "h-11 w-full rounded-xl border border-[#dce4f2] bg-white px-3 text-[14px] font-semibold text-[#172033] outline-none transition placeholder:text-[#a8b3c7] focus:border-[var(--bf-brand)] focus:ring-4 focus:ring-blue-100/70 disabled:cursor-not-allowed disabled:bg-[#f5f7fb] disabled:text-[#94a3b8]";

const text = (value: unknown, fallback = "-") => (value == null || value === "" ? fallback : String(value));
const num = (value: unknown) => Number(value ?? 0);

export function CategoryManagerDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<CategoryManagerTab>("categories");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState({ code: "", name: "", parentId: 0, zoneCode: "", clcHint: "", sortOrder: 0 });
  const [subItems, setSubItems] = useState<SubItem[]>([]);

  const categoriesQuery = useQuery({
    queryKey: ["catalog", "categories", "manager"],
    queryFn: () => catalogApi.categories({ limit: 500, offset: 0 }),
    enabled: open,
  });
  const subcategoriesQuery = useQuery({
    queryKey: ["catalog", "subcategories", "manager"],
    queryFn: () => catalogApi.subcategories({ limit: 1000, offset: 0 }),
    enabled: open,
  });

  const categories: AnyRecord[] = categoriesQuery.data?.items ?? [];
  const subcategories: AnyRecord[] = subcategoriesQuery.data?.items ?? [];

  const invalidateCatalogCategories = () => {
    queryClient.invalidateQueries({ queryKey: ["catalog", "categories"] });
    queryClient.invalidateQueries({ queryKey: ["catalog", "subcategories"] });
  };

  const resetForm = () => {
    setEditingId(null);
    setFormData({ code: "", name: "", parentId: 0, zoneCode: "", clcHint: "", sortOrder: 0 });
    setSubItems([]);
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (tab === "categories") {
        const body = {
          category_code: formData.code,
          category_name: formData.name,
          primary_zone_code: formData.zoneCode || undefined,
          clc_hint: formData.clcHint || undefined,
          sort_order: formData.sortOrder,
        };
        const result: AnyRecord = editingId ? await catalogApi.updateCategory(editingId, body) : await catalogApi.createCategory(body);
        const resultData = result.data && typeof result.data === "object" ? (result.data as AnyRecord) : {};
        const categoryId = result.id ?? resultData.id;

        if (categoryId) {
          for (const item of subItems) {
            if (item.name.trim()) {
              await catalogApi.createSubcategory({
                category_id: categoryId,
                subcategory_code: item.code || undefined,
                subcategory_name: item.name.trim(),
              });
            }
          }
        }
        return result;
      }

      const body = {
        category_id: formData.parentId,
        subcategory_code: formData.code,
        subcategory_name: formData.name,
        sort_order: formData.sortOrder,
      };
      return editingId ? catalogApi.updateSubcategory(editingId, body) : catalogApi.createSubcategory(body);
    },
    onSuccess: () => {
      setFormOpen(false);
      resetForm();
      invalidateCatalogCategories();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => (tab === "categories" ? catalogApi.deleteCategory(id) : catalogApi.deleteSubcategory(id)),
    onSuccess: () => invalidateCatalogCategories(),
  });

  function openCreate() {
    resetForm();
    setFormOpen(true);
  }

  function openEdit(row: AnyRecord) {
    setEditingId(Number(row.id));
    if (tab === "categories") {
      setFormData({
        code: String(row.category_code ?? ""),
        name: String(row.category_name ?? ""),
        parentId: 0,
        zoneCode: String(row.primary_zone_code ?? ""),
        clcHint: String(row.clc_hint ?? ""),
        sortOrder: Number(row.sort_order ?? 0),
      });
      const subs = subcategories.filter((item) => item.category_code === String(row.category_code));
      setSubItems(subs.map((item) => ({ code: String(item.subcategory_code ?? ""), name: String(item.subcategory_name ?? "") })));
    } else {
      setFormData({
        code: String(row.subcategory_code ?? ""),
        name: String(row.subcategory_name ?? ""),
        parentId: Number(row.category_id ?? 0),
        zoneCode: "",
        clcHint: "",
        sortOrder: Number(row.sort_order ?? 0),
      });
      setSubItems([]);
    }
    setFormOpen(true);
  }

  function addSubItem() {
    setSubItems((prev) => [...prev, { code: "", name: "" }]);
  }

  function removeSubItem(index: number) {
    setSubItems((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  }

  function updateSubItem(index: number, field: keyof SubItem, value: string) {
    setSubItems((prev) => prev.map((item, itemIndex) => (itemIndex === index ? { ...item, [field]: value } : item)));
  }

  const rows = tab === "categories" ? categories : subcategories;

  return (
    <FormDialog open={open} onOpenChange={onOpenChange} title="分类管理" className="!max-w-[720px]">
      <div className="flex gap-2 rounded-[16px] bg-[#f4f7fb] p-1 mb-4">
        {[
          ["categories", "一级分类"],
          ["subcategories", "二级分类"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`h-10 flex-1 rounded-[12px] text-sm font-black transition ${tab === key ? "bg-white text-[var(--bf-brand)] shadow-sm" : "text-[var(--bf-text-secondary)]"}`}
            onClick={() => setTab(key as CategoryManagerTab)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between mb-3">
        <span className="text-[13px] font-bold text-[var(--bf-text-secondary)]">
          {tab === "categories" ? `共 ${categories.length} 个一级分类` : `共 ${subcategories.length} 个二级分类`}
        </span>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-[10px] bg-[var(--bf-brand)] px-3 py-1.5 text-[12px] font-bold text-white hover:brightness-110 transition"
          onClick={openCreate}
        >
          <AppIcon name="plus" size={14} />
          {tab === "categories" ? "新增一级" : "新增二级"}
        </button>
      </div>

      <div className="space-y-2">
        {tab === "categories"
          ? categories.map((row) => (
              <div key={String(row.id)} className="flex items-center justify-between rounded-xl border border-[#e8edf6] bg-white px-4 py-3">
                <div>
                  <div className="text-[14px] font-bold text-[#101a35]">{text(row.category_name)}</div>
                  <div className="text-[12px] font-semibold text-[var(--bf-text-secondary)]">
                    {text(row.category_code)} · {num(row.book_title_count)} 本书
                  </div>
                </div>
                <div className="flex gap-1">
                  <button type="button" className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-[var(--bf-brand)] hover:bg-blue-50 transition" onClick={() => openEdit(row)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-[#dc2626] hover:bg-red-50 transition"
                    onClick={() => {
                      if (confirm(`确定删除「${text(row.category_name)}」？`)) deleteMutation.mutate(Number(row.id));
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))
          : subcategories.map((row) => (
              <div key={String(row.id)} className="flex items-center justify-between rounded-xl border border-[#e8edf6] bg-white px-4 py-3">
                <div>
                  <div className="text-[14px] font-bold text-[#101a35]">{text(row.subcategory_name)}</div>
                  <div className="text-[12px] font-semibold text-[var(--bf-text-secondary)]">
                    {text(row.subcategory_code)} · 归属 {text(row.category_name)} · {num(row.allocated_book_title_count)} 本书
                  </div>
                </div>
                <div className="flex gap-1">
                  <button type="button" className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-[var(--bf-brand)] hover:bg-blue-50 transition" onClick={() => openEdit(row)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    className="rounded-lg px-3 py-1.5 text-[12px] font-bold text-[#dc2626] hover:bg-red-50 transition"
                    onClick={() => {
                      if (confirm(`确定删除「${text(row.subcategory_name)}」？`)) deleteMutation.mutate(Number(row.id));
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
        {rows.length === 0 && <div className="text-center text-[13px] font-semibold text-[var(--bf-text-secondary)] py-6">暂无分类，点击上方按钮新增</div>}
      </div>

      <FormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={editingId ? (tab === "categories" ? "编辑一级分类" : "编辑二级分类") : tab === "categories" ? "新增一级分类" : "新增二级分类"}
      >
        <form
          className="space-y-3 max-h-[70vh] overflow-y-auto"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
        >
          {tab === "subcategories" && (
            <select className={fieldClass()} value={formData.parentId} onChange={(event) => setFormData((data) => ({ ...data, parentId: Number(event.target.value) }))} required>
              <option value={0}>请选择所属一级分类 *</option>
              {categories.map((category) => (
                <option key={String(category.id)} value={Number(category.id)}>
                  {text(category.category_name)} ({text(category.category_code)})
                </option>
              ))}
            </select>
          )}

          <div className="grid grid-cols-2 gap-3">
            <input
              className={fieldClass()}
              placeholder={tab === "categories" ? "分类编号 *" : "二级编号 *"}
              value={formData.code}
              onChange={(event) => setFormData((data) => ({ ...data, code: event.target.value }))}
              required
              disabled={!!editingId}
            />
            <input
              className={fieldClass()}
              placeholder="分类名称 *"
              value={formData.name}
              onChange={(event) => setFormData((data) => ({ ...data, name: event.target.value }))}
              required
            />
          </div>

          {tab === "categories" && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <input
                  className={fieldClass()}
                  placeholder="主分区编号（可选）"
                  value={formData.zoneCode}
                  onChange={(event) => setFormData((data) => ({ ...data, zoneCode: event.target.value }))}
                />
                <input
                  className={fieldClass()}
                  placeholder="CLC 提示（可选）"
                  value={formData.clcHint}
                  onChange={(event) => setFormData((data) => ({ ...data, clcHint: event.target.value }))}
                />
              </div>

              <div className="rounded-[14px] border border-[#e8edf6] bg-[#fbfcff] p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-black text-[#31405f]">二级分类</span>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-[8px] border border-[#dce4f2] px-2 py-1 text-[11px] font-bold text-[var(--bf-text-secondary)] hover:bg-[#f1f5f9] transition"
                    onClick={addSubItem}
                  >
                    <AppIcon name="plus" size={12} />
                    添加
                  </button>
                </div>

                {subItems.length === 0 ? (
                  <p className="text-[12px] font-semibold text-[#94a3b8]">暂未添加，保存后可另行新增</p>
                ) : (
                  <div className="space-y-2">
                    {subItems.map((item, index) => (
                      <div key={index} className="flex items-center gap-3">
                        <input
                          className="h-9 flex-[2] rounded-[10px] border border-[#dce4f2] bg-white px-3 text-[13px] font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)]"
                          placeholder="二级名称"
                          value={item.name}
                          onChange={(event) => updateSubItem(index, "name", event.target.value)}
                        />
                        <input
                          className="h-9 flex-1 rounded-[10px] border border-[#dce4f2] bg-white px-3 text-[12px] font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)]"
                          placeholder="编号"
                          value={item.code}
                          onChange={(event) => updateSubItem(index, "code", event.target.value)}
                        />
                        <button
                          type="button"
                          className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-[8px] text-[#94a3b8] hover:bg-red-50 hover:text-[#dc2626] transition"
                          onClick={() => removeSubItem(index)}
                          title="移除"
                        >
                          <AppIcon name="close" size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <ActionButton
              variant="secondary"
              onClick={() => {
                setFormOpen(false);
                setSubItems([]);
              }}
            >
              取消
            </ActionButton>
            <ActionButton type="submit" icon="check" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "保存中" : "保存"}
            </ActionButton>
          </div>
        </form>
      </FormDialog>
    </FormDialog>
  );
}
