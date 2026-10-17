import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { libraryApi } from "@/api/library";
import { locationsApi } from "@/api/locations";
import { FeatureIcon } from "@/components/icons/FeatureIcon";
import { ActionButton } from "@/components/ui/ActionButton";
import { FormDialog } from "@/components/ui/FormDialog";
import { PageCard } from "@/components/ui/PageCard";
import { ZoneLayoutEditor } from "@/components/zone/ZoneLayoutEditor";
import { formatNumber } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { AnyRecord } from "@/types/api";
import rhythm from "@/styles/AdminRhythm.module.css";

function InfoItem({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="min-h-[88px] min-w-0 rounded-[15px] bg-[#f8fbff] px-5 py-4 flex flex-col justify-center">
      <div className="text-[13px] font-semibold text-[var(--bf-text-secondary)]">{label}</div>
      <div className="mt-2 break-words text-[17px] font-black leading-snug text-[#071334]" title={String(value ?? "-")}>{String(value ?? "-")}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="grid gap-1.5"><span className="text-[13px] font-black text-[#3a4d73]">{label}</span>{children}</label>;
}

function SettingsMainCard({
  icon,
  title,
  action,
  children,
  gridClassName = "md:grid-cols-2 xl:grid-cols-4",
}: {
  icon: string;
  title: string;
  action?: ReactNode;
  children: ReactNode;
  gridClassName?: string;
}) {
  return (
    <PageCard className={rhythm.settingsCard} bodyClassName="p-6">
      <div className="flex items-start gap-6">
        <FeatureIcon name={icon} tone="blue" size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-[21px] font-black text-[#071334]">{title}</h2>
            {action ? <div className="shrink-0">{action}</div> : null}
          </div>
          <div className={cn("mt-5 grid grid-cols-1 gap-4", gridClassName)}>{children}</div>
        </div>
      </div>
    </PageCard>
  );
}

export function SettingsPage() {
  const queryClient = useQueryClient();

  function FloorEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    const [newFloor, setNewFloor] = useState("");
    const floors: string[] = value.split(/[,，、\n\r]+/).map((f: string) => f.trim()).filter(Boolean);
    function setFloors(list: string[]) { onChange(list.join("、")); }
    return (
      <div className="space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {floors.map((f) => (
            <span key={f} className="inline-flex items-center gap-0.5 rounded-[8px] border border-[#dce4f2] bg-white px-2.5 py-1 text-[13px] font-bold text-[#172033]">
              {f}
              <button type="button" className="ml-0.5 text-[14px] text-[#94a3b8] hover:text-[#ef4444] leading-none" onClick={() => setFloors(floors.filter((x) => x !== f))}>×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input className="h-9 w-24 rounded-[10px] border border-[#dce4f2] bg-white px-2.5 text-[13px] font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)]" placeholder="如 F3" value={newFloor} onChange={(e) => setNewFloor(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (newFloor.trim()) { setFloors([...floors, newFloor.trim()]); setNewFloor(""); } } }} />
          <button type="button" className="h-9 rounded-[10px] border border-[#dce4f2] bg-[#f8fafc] px-3 text-[12px] font-bold text-[#475569] hover:bg-white transition" onClick={() => { if (newFloor.trim()) { setFloors([...floors, newFloor.trim()]); setNewFloor(""); } }}>＋ 添加</button>
        </div>
      </div>
    );
  }

  const profile = useQuery({ queryKey: ["library", "profile"], queryFn: libraryApi.profile });
  const zones = useQuery({ queryKey: ["locations", "zones"], queryFn: () => locationsApi.zones({ limit: 100 }) });

  const profileData: AnyRecord = profile.data ?? {};

  // ── dialog open state ──────────────────────────────────────────────
  const [profileFormOpen, setProfileFormOpen] = useState(false);
  const [layoutEditorOpen, setLayoutEditorOpen] = useState(false);
  const [runtimeFormOpen, setRuntimeFormOpen] = useState(false);

  // ── form state ─────────────────────────────────────────────────────
  const [profileForm, setProfileForm] = useState<AnyRecord>({});
  const [runtimeForm, setRuntimeForm] = useState<AnyRecord>({});

  // ── helpers ────────────────────────────────────────────────────────
  const refreshProfile = async () => {
    await queryClient.invalidateQueries({ queryKey: ["library", "profile"] });
  };

  const text = (value: unknown, fallback = "") => String(value ?? fallback);
  const num = (value: unknown, fallback = 0) => Number(value ?? fallback);

  // ── open handlers ──────────────────────────────────────────────────
  const openProfileEdit = () => {
    setProfileForm({
      library_name: text(profileData.library_name),
      library_type: text(profileData.library_type),
      building_area_sqm: num(profileData.building_area_sqm),
      open_floors: text(profileData.open_floors),
    });
    setProfileFormOpen(true);
  };

  const openRuntimeEdit = () => {
    setRuntimeForm({
      address: text(profileData.address),
      opening_hours: text(profileData.opening_hours),
      phone: text(profileData.phone),
      service_email: text(profileData.service_email),
    });
    setRuntimeFormOpen(true);
  };

  // ── mutations ──────────────────────────────────────────────────────
  const profileMutation = useMutation({
    mutationFn: (body: AnyRecord) => libraryApi.updateProfile(body),
    onSuccess: async () => {
      toast.success("图书馆基础信息已更新");
      setProfileFormOpen(false);
      await refreshProfile();
    },
  });

  const runtimeMutation = useMutation({
    mutationFn: (body: AnyRecord) => libraryApi.updateSettings({
      settings: {
        "library.address": String(body.address ?? ""),
        "library.open_hours": String(body.opening_hours ?? ""),
        "library.phone": String(body.phone ?? ""),
        "library.service_email": String(body.service_email ?? ""),
      },
    }),
    onSuccess: async () => {
      toast.success("系统运行设置已更新");
      setRuntimeFormOpen(false);
      await refreshProfile();
    },
  });

  // ── action buttons ─────────────────────────────────────────────────
  const profileEditBtn = (
    <ActionButton variant="secondary" onClick={openProfileEdit}>
      编辑
</ActionButton>
  );

  const spaceEditBtn = (
    <ActionButton variant="secondary" onClick={() => setLayoutEditorOpen(true)}>
      编辑
</ActionButton>
  );

  const runtimeEditBtn = (
    <ActionButton variant="secondary" onClick={openRuntimeEdit}>
      编辑
</ActionButton>
  );

  return (
    <div className={rhythm.scrollPage}>
      <div className="flex h-[52px] items-center"><p className="text-[18px] font-bold leading-relaxed text-[#31405f]">管理图书馆基础信息、馆内空间配置和系统运行参数。</p></div>

      {/* ── 栏目 1：图书馆基础信息 ────────────────────────────────────── */}
      <SettingsMainCard icon="settings" title="图书馆基础信息" action={profileEditBtn}>
        <InfoItem label="图书馆名称" value={profileData.library_name} />
        <InfoItem label="图书馆类型" value={profileData.library_type} />
        <InfoItem label="建筑面积" value={`${formatNumber(profileData.building_area_sqm)} 平方米`} />
        <InfoItem label="开放楼层" value={profileData.open_floors} />
      </SettingsMainCard>

      {/* ── 栏目 2：馆内空间配置 ──────────────────────────────────────── */}
      <SettingsMainCard icon="catalog" title="馆内空间配置" action={spaceEditBtn}>
        <InfoItem label="空间分区" value={`${formatNumber(profileData.zone_count ?? (zones.isError ? undefined : zones.data?.total ?? zones.data?.items?.length))} 个`} />
        <InfoItem label="正式馆藏书架" value={`${formatNumber(profileData.shelf_count)} 组`} />
        <InfoItem label="预约暂存架" value={`${formatNumber(profileData.reservation_shelf_count)} 组`} />
        <InfoItem label="后台周转架" value={`${formatNumber(profileData.turnover_shelf_count)} 组`} />
      </SettingsMainCard>

      {/* ── 栏目 3：系统运行设置 ──────────────────────────────────────── */}
      <SettingsMainCard icon="data" title="系统运行设置" action={runtimeEditBtn}>
        <InfoItem label="图书馆地址" value={profileData.address} />
        <InfoItem label="开放时间" value={profileData.opening_hours} />
        <InfoItem label="服务电话" value={profileData.phone} />
        <InfoItem label="服务邮箱" value={profileData.service_email} />
      </SettingsMainCard>

      {/* ── FormDialog：图书馆基础信息 ────────────────────────────────── */}
      <FormDialog open={profileFormOpen} onOpenChange={setProfileFormOpen} title="编辑图书馆基础信息">
        <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); profileMutation.mutate(profileForm); }}>
          <Field label="图书馆名称">
            <input className="bf-input" value={text(profileForm.library_name)} onChange={(event) => setProfileForm((prev) => ({ ...prev, library_name: event.target.value }))} required />
          </Field>
          <Field label="图书馆类型">
            <input className="bf-input" value={text(profileForm.library_type)} onChange={(event) => setProfileForm((prev) => ({ ...prev, library_type: event.target.value }))} />
          </Field>
          <Field label="建筑面积（平方米）">
            <input className="bf-input" type="number" min="0" value={num(profileForm.building_area_sqm)} onChange={(event) => setProfileForm((prev) => ({ ...prev, building_area_sqm: Number(event.target.value) }))} />
          </Field>
          <Field label="开放楼层">
            <FloorEditor value={text(profileForm.open_floors)} onChange={(v) => setProfileForm((prev) => ({ ...prev, open_floors: v }))} />
          </Field>
          <div className="mt-5 flex justify-end gap-3">
            <ActionButton type="button" variant="ghost" onClick={() => setProfileFormOpen(false)}>取消</ActionButton>
            <ActionButton type="submit" variant="primary" disabled={profileMutation.isPending}>{profileMutation.isPending ? "保存中" : "保存"}</ActionButton>
          </div>
        </form>
      </FormDialog>

      {/* ── ZoneLayoutEditor：平面布局 ────────────────────────────────── */}
      <ZoneLayoutEditor open={layoutEditorOpen} onOpenChange={setLayoutEditorOpen} />

      {/* ── FormDialog：系统运行设置 ──────────────────────────────────── */}
      <FormDialog open={runtimeFormOpen} onOpenChange={setRuntimeFormOpen} title="编辑系统运行设置">
        <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); runtimeMutation.mutate(runtimeForm); }}>
          <Field label="图书馆地址">
            <input className="bf-input" value={text(runtimeForm.address)} onChange={(event) => setRuntimeForm((prev) => ({ ...prev, address: event.target.value }))} />
          </Field>
          <Field label="开放时间">
            <input className="bf-input" value={text(runtimeForm.opening_hours)} onChange={(event) => setRuntimeForm((prev) => ({ ...prev, opening_hours: event.target.value }))} />
          </Field>
          <Field label="服务电话">
            <input className="bf-input" value={text(runtimeForm.phone)} onChange={(event) => setRuntimeForm((prev) => ({ ...prev, phone: event.target.value }))} />
          </Field>
          <Field label="服务邮箱">
            <input className="bf-input" type="email" value={text(runtimeForm.service_email)} onChange={(event) => setRuntimeForm((prev) => ({ ...prev, service_email: event.target.value }))} />
          </Field>
          <div className="mt-5 flex justify-end gap-3">
            <ActionButton type="button" variant="ghost" onClick={() => setRuntimeFormOpen(false)}>取消</ActionButton>
            <ActionButton type="submit" variant="primary" disabled={runtimeMutation.isPending}>{runtimeMutation.isPending ? "保存中" : "保存"}</ActionButton>
          </div>
        </form>
      </FormDialog>
    </div>
  );
}
