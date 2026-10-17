import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stage, Layer, Rect, Text, Group, Transformer } from "react-konva";
import type Konva from "konva";
import { libraryApi } from "@/api/library";
import { locationsApi } from "@/api/locations";
import { ActionButton } from "@/components/ui/ActionButton";
import { FormDialog } from "@/components/ui/FormDialog";
import { toast } from "sonner";
import type { AnyRecord } from "@/types/api";

// ── helpers ──

const PX_PER_M = 16;

function text(v: unknown, fb = "") { return String(v ?? fb); }
function num(v: unknown, fb = 0) { return Number(v ?? fb); }
function records(v: unknown): AnyRecord[] { return Array.isArray(v) ? v as AnyRecord[] : []; }
function fieldClass() { return "h-10 w-full rounded-[12px] border border-[#dce4f2] bg-white px-3 text-sm font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)] focus:ring-4 focus:ring-blue-50"; }
function smallFieldClass() { return "h-9 w-full rounded-[10px] border border-[#dce4f2] bg-white px-2.5 text-[12px] font-semibold text-[#172033] outline-none focus:border-[var(--bf-brand)]"; }

const ZONE_COLORS = ["#e8f4f8", "#fef3c7", "#fce7f3", "#dcfce7", "#e0e7ff", "#f5f5f4", "#ffe4e6", "#ccfbf1"];
const SHELF_FILL = "#64748b";
const SHELF_TYPE_COLORS: Record<string, string> = { formal: "#64748b", reservation: "#3b82f6", turnover: "#16a34a" };
const SNAP_GRID = 20;

// ── main component ──

export function ZoneLayoutEditor({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const stageRef = useRef<Konva.Stage>(null);
  const trRef = useRef<Konva.Transformer>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 1200, h: 800 });
  const [stageScale, setStageScale] = useState(1);
  const [stageOffset, setStageOffset] = useState({ x: 0, y: 0 });

  const treeQuery = useQuery({ queryKey: ["locations", "tree"], queryFn: () => locationsApi.tree(), enabled: open });
  const profileQuery = useQuery({ queryKey: ["library", "profile"], queryFn: () => libraryApi.profile(), enabled: open });
  const zones = records(treeQuery.data?.items);
  const allShelves = zones.flatMap((z) => records(z.shelves).map((s) => ({ ...s, _zone_code: z.zone_code, _zone_name: z.zone_name, _zone_color: z.color })));
  const profile = profileQuery.data ?? {};
  const profileFloors = text(profile.open_floors).split(/[,，、\n\r]+/).map((f: string) => f.trim()).filter(Boolean);
  const hasProfileFloors = profileFloors.length > 0;

  const [zoneItems, setZoneItems] = useState<AnyRecord[]>([]);
  const [shelfItems, setShelfItems] = useState<AnyRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<AnyRecord | null>(null);
  const [selectedShelf, setSelectedShelf] = useState<AnyRecord | null>(null);
  const [hoveredShelf, setHoveredShelf] = useState<{ id: string; x: number; y: number; code: string } | null>(null);
  const [hoveredZone, setHoveredZone] = useState<{ id: string; x: number; y: number; name: string } | null>(null);
  const [activeFloor, setActiveFloor] = useState("F1");
  const [buildDims, setBuildDims] = useState<Record<string, { w: number; h: number }>>({});
  const activeDims = buildDims[activeFloor] ?? { w: 60, h: 45 };
  function setActiveDims(w: number, h: number) { setBuildDims((prev) => ({ ...prev, [activeFloor]: { w, h } })); }
  const buildPxW = activeDims.w * PX_PER_M;
  const buildPxH = activeDims.h * PX_PER_M;

  const [zoneFormOpen, setZoneFormOpen] = useState(false);
  const [shelfFormOpen, setShelfFormOpen] = useState(false);
  const [editingZoneId, setEditingZoneId] = useState<number | null>(null);
  const [editingShelfId, setEditingShelfId] = useState<number | null>(null);

  // resize canvas to fill container
  useEffect(() => {
    if (!open) return;
    function resize() {
      if (containerRef.current) {
        setCanvasSize({ w: containerRef.current.clientWidth, h: containerRef.current.clientHeight });
      }
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [open]);

  useEffect(() => {
    if (zones.length) {
      setZoneItems(zones.map((z) => ({ ...z, id: `z-${z.id}`, _type: "zone" })));
      setShelfItems(allShelves.map((s: AnyRecord) => ({ ...s, id: `s-${s.id}`, _type: "shelf" })));
    }
  }, [zones.length, treeQuery.dataUpdatedAt]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["locations"] });
  const floors = hasProfileFloors ? profileFloors.sort() : Array.from(new Set([...zones.map((z) => text(z.floor, "F1")), "F1"])).filter(Boolean).sort();
  const visibleZoneItems = zoneItems.filter((zone) => text(zone.floor, "F1") === activeFloor);
  const visibleShelfItems = shelfItems.filter((shelf) => text(shelf.floor, "F1") === activeFloor);

  const updateFloorsMutation = useMutation({
    mutationFn: (newFloors: string[]) => libraryApi.updateProfile({ open_floors: newFloors.join("、") }),
    onSuccess: () => { toast.success("楼层已更新"); queryClient.invalidateQueries({ queryKey: ["library", "profile"] }); },
    onError: () => { toast.error("楼层更新失败"); },
  });
  function handleUpdateFloors(newFloors: string[]) {
    updateFloorsMutation.mutate(newFloors);
  }

  const saveLayoutMutation = useMutation({
    mutationFn: () => {
      const zs = zoneItems.map((z) => ({ id: String(z.id).replace("z-", ""), pos_x: z.pos_x ?? z.x, pos_y: z.pos_y ?? z.y, width: z.width, height: z.height }));
      const ss = shelfItems.map((s) => ({ id: String(s.id).replace("s-", ""), pos_x: s.pos_x ?? s.x, pos_y: s.pos_y ?? s.y, width: s.width, height: s.height, rotation: s.rotation ?? 0 }));
      return locationsApi.saveLayout({ zones: zs, shelves: ss });
    },
    onSuccess: () => { toast.success("布局已保存"); invalidate(); },
    onError: () => { toast.error("保存失败，请重试"); },
  });

  function snap(v: number) { return Math.round(v / SNAP_GRID) * SNAP_GRID; }

  function handleDragEnd(id: string, x: number, y: number) {
    const sx = snap(x); const sy = snap(y);
    if (id.startsWith("z-")) {
      setZoneItems((prev) => prev.map((z) => z.id === id ? { ...z, pos_x: sx, pos_y: sy } : z));
    } else {
      setShelfItems((prev) => prev.map((s) => s.id === id ? { ...s, pos_x: sx, pos_y: sy } : s));
    }
  }

  function handleTransformEnd(id: string, node: Konva.Group) {
    if (id.startsWith("z-")) {
      const r = node.getClientRect();
      setZoneItems((prev) => prev.map((z) => z.id === id ? { ...z, pos_x: snap(r.x), pos_y: snap(r.y), width: Math.max(30, snap(r.width)), height: Math.max(20, snap(r.height)) } : z));
    } else {
      setShelfItems((prev) => prev.map((s) => s.id === id ? { ...s, pos_x: snap(node.x()), pos_y: snap(node.y()) } : s));
    }
  }

  function handleSelect(id: string) {
    setSelectedId(id);
    const stage = stageRef.current; const tr = trRef.current;
    if (!stage || !tr) return;
    const node = stage.findOne(`#${id}`);
    if (node) tr.nodes([node]);
    if (id.startsWith("z-")) {
      const z = zoneItems.find((x) => x.id === id);
      setSelectedZone(z ?? null); setSelectedShelf(null);
    } else {
      const s = shelfItems.find((x) => x.id === id);
      setSelectedShelf(s ?? null); setSelectedZone(null);
    }
  }

  function clearSelection() { setSelectedId(null); setSelectedZone(null); setSelectedShelf(null); if (trRef.current) trRef.current.nodes([]); }

  function updateSelectedZoneProp(key: string, val: number) {
    if (!selectedZone) return;
    setZoneItems((prev) => prev.map((z) => z.id === selectedZone.id ? { ...z, [key]: val } : z));
    setSelectedZone((prev) => prev ? { ...prev, [key]: val } : null);
  }

  function updateSelectedShelfProp(key: string, val: number) {
    if (!selectedShelf) return;
    setShelfItems((prev) => prev.map((s) => s.id === selectedShelf.id ? { ...s, [key]: val } : s));
    setSelectedShelf((prev) => prev ? { ...prev, [key]: val } : null);
  }

  // delete mutations — properly wired with invalidation
  const deleteZoneMutation = useMutation({
    mutationFn: (zoneId: number) => locationsApi.deleteZone(zoneId),
    onSuccess: () => invalidate(),
  });
  const deleteShelfMutation = useMutation({
    mutationFn: (shelfId: number) => locationsApi.deleteShelf(shelfId),
    onSuccess: () => invalidate(),
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#f1f5f9]">
      {/* top bar */}
      <div className="flex items-center gap-4 bg-white border-b border-[#e2e8f0] px-5 py-3 shadow-sm">
        <span className="text-[16px] font-black text-[#0f172a]">馆内平面布局</span>
        <span className="text-[12px] font-semibold text-[#94a3b8]">|</span>
        <div className="flex items-center overflow-hidden rounded-[10px] border border-[#dce4f2] bg-[#f8fafc]">
          {floors.map((floor) => (
            <button
              key={floor}
              className={activeFloor === floor ? "h-8 bg-[var(--bf-brand)] px-4 text-[12px] font-black text-white" : "h-8 px-4 text-[12px] font-black text-[#475569] hover:bg-white"}
              onClick={() => { setActiveFloor(floor); clearSelection(); }}
              type="button"
            >
              {floor}
            </button>
          ))}
          <button type="button" className="h-8 w-8 flex items-center justify-center text-[14px] font-black text-[#475569] hover:bg-white transition" onClick={() => { const next = `F${floors.length + 1}`; setBuildDims((prev) => ({ ...prev, [next]: { w: activeDims.w, h: activeDims.h } })); handleUpdateFloors([...floors, next]); setActiveFloor(next); }} title="新增楼层">＋</button>
          {floors.length > 1 ? <button type="button" className="h-8 w-8 flex items-center justify-center text-[14px] font-black text-[#ef4444] hover:bg-red-50 transition" onClick={() => { const rest = floors.filter((f) => f !== activeFloor); if (rest.length) { handleUpdateFloors(rest); if (activeFloor === floors[floors.length - 1]) setActiveFloor(rest[rest.length - 1]); } }} title="删除当前楼层">−</button> : null}
        </div>
        <button type="button" className="inline-flex items-center gap-1.5 rounded-[10px] bg-[var(--bf-brand)] px-3 py-1.5 text-[12px] font-bold text-white hover:brightness-110 transition" onClick={() => { setEditingZoneId(null); setZoneFormOpen(true); }}>＋ 新增分区</button>
        <button type="button" className="inline-flex items-center gap-1.5 rounded-[10px] border border-[#dce4f2] bg-white px-3 py-1.5 text-[12px] font-bold text-[#475569] hover:bg-[#f1f5f9] transition" onClick={() => { setEditingShelfId(null); setShelfFormOpen(true); }}>＋ 新增书架</button>
        <span className="text-[12px] font-semibold text-[#94a3b8]">|</span>
        <button type="button" className="inline-flex items-center justify-center h-7 w-7 rounded-[8px] border border-[#dce4f2] bg-white text-[14px] font-black text-[#475569] hover:bg-[#f1f5f9] transition disabled:opacity-30" disabled={stageScale <= 0.3} onClick={() => { setStageScale((s) => Math.max(0.2, s - 0.2)); }}>−</button>
        <span className="text-[12px] font-black text-[#475569] w-10 text-center">{Math.round(stageScale * 100)}%</span>
        <button type="button" className="inline-flex items-center justify-center h-7 w-7 rounded-[8px] border border-[#dce4f2] bg-white text-[14px] font-black text-[#475569] hover:bg-[#f1f5f9] transition disabled:opacity-30" disabled={stageScale >= 2} onClick={() => { setStageScale((s) => Math.min(2, s + 0.2)); }}>＋</button>
        <button type="button" className="inline-flex items-center gap-1 rounded-[8px] border border-[#dce4f2] bg-white px-2 py-1 text-[11px] font-bold text-[#475569] hover:bg-[#f1f5f9] transition" onClick={() => { setStageScale(1); setStageOffset({ x: 0, y: 0 }); }}>1:1</button>
        <span className="text-[12px] font-semibold text-[#94a3b8]">|</span>
        <span className="text-[11px] font-semibold text-[#64748b]">宽</span>
        <input className="h-7 w-14 rounded-[8px] border border-[#dce4f2] px-1.5 text-center text-[12px] font-bold text-[#172033] outline-none focus:border-[var(--bf-brand)]" type="number" value={activeDims.w} min={5} max={200} onChange={(e) => setActiveDims(Math.max(5, Number(e.target.value) || 5), activeDims.h)} />
        <span className="text-[11px] font-semibold text-[#64748b]">× 高</span>
        <input className="h-7 w-14 rounded-[8px] border border-[#dce4f2] px-1.5 text-center text-[12px] font-bold text-[#172033] outline-none focus:border-[var(--bf-brand)]" type="number" value={activeDims.h} min={5} max={200} onChange={(e) => setActiveDims(activeDims.w, Math.max(5, Number(e.target.value) || 5))} />
        <span className="text-[11px] font-semibold text-[#64748b]">m</span>
        <div className="ml-auto flex gap-2">
          <ActionButton variant="secondary" size="sm" onClick={() => onOpenChange(false)}>退出</ActionButton>
          <ActionButton size="sm" icon="check" disabled={saveLayoutMutation.isPending} onClick={() => saveLayoutMutation.mutate()}>{saveLayoutMutation.isPending ? "保存中" : "保存布局"}</ActionButton>
        </div>
      </div>

      {/* main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* canvas */}
        <div ref={containerRef} className="flex-1 relative overflow-hidden m-4 rounded-[16px] border border-[#e2e8f0] bg-white shadow-sm">
          {treeQuery.isLoading ? (
            <div className="flex h-full items-center justify-center text-sm font-semibold text-[var(--bf-text-secondary)]">加载中…</div>
          ) : zones.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-sm font-semibold text-[var(--bf-text-secondary)]">
              <span>暂无分区数据</span>
              <button type="button" className="rounded-[10px] bg-[var(--bf-brand)] px-4 py-2 text-[13px] font-bold text-white" onClick={() => { setEditingZoneId(null); setZoneFormOpen(true); }}>创建第一个分区</button>
            </div>
          ) : (
            <Stage ref={stageRef} width={canvasSize.w} height={canvasSize.h} scaleX={stageScale} scaleY={stageScale} x={stageOffset.x} y={stageOffset.y} onMouseDown={(e) => { if (e.target === e.target.getStage()) clearSelection(); }}>
              <Layer>
                <Rect x={24} y={24} width={buildPxW} height={buildPxH} fill="#fffdf8" stroke="#1f2937" strokeWidth={3} cornerRadius={4} listening={false} />
                {visibleZoneItems.map((z) => (
                  <Group key={String(z.id)} id={String(z.id)} x={num(z.pos_x)} y={num(z.pos_y)} scaleX={1} scaleY={1} draggable onDragEnd={(e) => handleDragEnd(String(z.id), e.target.x(), e.target.y())} onClick={() => handleSelect(String(z.id))} onTap={() => handleSelect(String(z.id))} onMouseEnter={() => { setHoveredZone({ id: String(z.id), x: num(z.pos_x), y: num(z.pos_y), name: text(z.zone_name) }); }} onMouseLeave={() => setHoveredZone(null)}>
                    <Rect x={0} y={0} width={num(z.width, 200)} height={num(z.height, 150)} fill={text(z.color, ZONE_COLORS[zoneItems.indexOf(z) % ZONE_COLORS.length])} stroke={selectedId === z.id ? "#3b82f6" : "#cbd5e1"} strokeWidth={selectedId === z.id ? 2.5 : 1} cornerRadius={10} shadowColor={selectedId === z.id ? "rgba(59,130,246,0.2)" : "transparent"} shadowBlur={8} />
                  </Group>
                ))}
                {visibleShelfItems.map((s) => {
                  const shelfColor = SHELF_TYPE_COLORS[text(s.shelf_type, "formal")] || SHELF_FILL;
                  const shelfW = 54;
                  const shelfH = 18;
                  return (
                    <Group key={String(s.id)} id={String(s.id)} x={num(s.pos_x)} y={num(s.pos_y)} scaleX={1} scaleY={1} rotation={num(s.rotation)} draggable onDragEnd={(e) => handleDragEnd(String(s.id), e.target.x(), e.target.y())} onClick={() => handleSelect(String(s.id))} onTap={() => handleSelect(String(s.id))} onMouseEnter={() => { setHoveredShelf({ id: String(s.id), x: num(s.pos_x), y: num(s.pos_y), code: text(s.shelf_code) }); }} onMouseLeave={() => setHoveredShelf(null)}>
                      <Rect x={0} y={0} width={shelfW} height={shelfH} fill={shelfColor} stroke={selectedId === s.id ? "#fbbf24" : "#1e293b"} strokeWidth={selectedId === s.id ? 2 : 0.5} cornerRadius={4} />
                    </Group>
                  );
                })}
                {hoveredShelf ? <Text x={hoveredShelf.x + 4} y={hoveredShelf.y - 16} text={hoveredShelf.code} fontSize={11} fill="#0f172a" fontStyle="bold" listening={false} /> : null}
                {hoveredZone ? <Text x={hoveredZone.x + 14} y={hoveredZone.y - 16} text={hoveredZone.name} fontSize={11} fill="#0f172a" fontStyle="bold" listening={false} /> : null}
                <Transformer ref={trRef} boundBoxFunc={(ob, nb) => (nb.width < 30 || nb.height < 20 ? ob : nb)} onTransformEnd={() => { const nodes = trRef.current?.nodes() || []; nodes.forEach((n) => { const id = n.id(); if (id) handleTransformEnd(id, n as Konva.Group); }); }} />
              </Layer>
            </Stage>
          )}
        </div>

        {/* right sidebar */}
        <div className="w-[320px] flex flex-col gap-3 bg-white border-l border-[#e2e8f0] p-4 overflow-y-auto">
          <div className="flex items-center gap-3 text-[11px] font-semibold text-[#64748b]">
            <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: SHELF_TYPE_COLORS.formal }} /> 正式</span>
            <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: SHELF_TYPE_COLORS.reservation }} /> 预约</span>
            <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: SHELF_TYPE_COLORS.turnover }} /> 周转</span>
          </div>

          {selectedZone ? (
            <div className="rounded-[14px] border border-[#e8edf6] bg-[#fbfcff] p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[14px] font-black text-[#0f172a]">分区属性</span>
                <button type="button" className="text-[11px] font-bold text-[#94a3b8] hover:text-[#dc2626]" onClick={clearSelection}>取消选中</button>
              </div>
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: text(selectedZone.color, "#e8f4f8") }} />
                  <span className="text-[13px] font-bold text-[#101a35]">{text(selectedZone.zone_name)}</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] font-bold text-[#94a3b8]">X <input className={smallFieldClass()} type="number" value={num(selectedZone.pos_x)} onChange={(e) => updateSelectedZoneProp("pos_x", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">Y <input className={smallFieldClass()} type="number" value={num(selectedZone.pos_y)} onChange={(e) => updateSelectedZoneProp("pos_y", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">宽 <input className={smallFieldClass()} type="number" value={num(selectedZone.width)} onChange={(e) => updateSelectedZoneProp("width", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">高 <input className={smallFieldClass()} type="number" value={num(selectedZone.height)} onChange={(e) => updateSelectedZoneProp("height", Number(e.target.value))} /></label>
                </div>
              </div>
            </div>
          ) : selectedShelf ? (
            <div className="rounded-[14px] border border-[#e8edf6] bg-[#fbfcff] p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[14px] font-black text-[#0f172a]">书架属性</span>
                <button type="button" className="text-[11px] font-bold text-[#94a3b8] hover:text-[#dc2626]" onClick={clearSelection}>取消选中</button>
              </div>
              <div className="space-y-2.5">
                <span className="text-[13px] font-bold text-[#101a35]">{text(selectedShelf.shelf_code)}</span>
                <span className="text-[11px] font-semibold text-[#64748b]">归属 {text(selectedShelf._zone_name || selectedShelf.zone_name)}</span>
                <span className="text-[11px] font-semibold text-[#64748b]">
                  类型{" "}
                  <span className="inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ backgroundColor: SHELF_TYPE_COLORS[text(selectedShelf.shelf_type, "formal")] || SHELF_FILL }} />{" "}
                  {text(selectedShelf.shelf_type) === "reservation" ? "预约暂存" : text(selectedShelf.shelf_type) === "turnover" ? "后台周转" : "正式馆藏"}
                </span>
                <div className="grid grid-cols-2 gap-2">
                  <label className="text-[11px] font-bold text-[#94a3b8]">X <input className={smallFieldClass()} type="number" value={num(selectedShelf.pos_x)} onChange={(e) => updateSelectedShelfProp("pos_x", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">Y <input className={smallFieldClass()} type="number" value={num(selectedShelf.pos_y)} onChange={(e) => updateSelectedShelfProp("pos_y", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">宽 <input className={smallFieldClass()} type="number" value={num(selectedShelf.width)} onChange={(e) => updateSelectedShelfProp("width", Number(e.target.value))} /></label>
                  <label className="text-[11px] font-bold text-[#94a3b8]">高 <input className={smallFieldClass()} type="number" value={num(selectedShelf.height)} onChange={(e) => updateSelectedShelfProp("height", Number(e.target.value))} /></label>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-[14px] border border-dashed border-[#e2e8f0] bg-[#f8fafc] p-4 text-center text-[12px] font-semibold text-[#94a3b8]">
              点击画布中的区域或书架<br />可查看和编辑属性
            </div>
          )}

          {/* zone list */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-black text-[#31405f]">分区列表</span>
              <button type="button" className="text-[11px] font-bold text-[var(--bf-brand)]" onClick={() => { setEditingZoneId(null); setZoneFormOpen(true); }}>＋ 新增</button>
            </div>
            <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
              {zones.filter((z) => text(z.floor, "F1") === activeFloor).map((z) => (
                <div key={String(z.id)} className="flex items-center justify-between rounded-lg border border-[#e8edf6] bg-white px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="inline-block h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: text(z.color, "#e8f4f8") }} />
                    <span className="text-[12px] font-bold text-[#101a35] truncate">{text(z.zone_name)}</span>
                    <span className="text-[11px] font-semibold text-[#94a3b8] shrink-0">{records(z.shelves).length} 架</span>
                  </div>
                  <div className="flex gap-0.5 shrink-0">
                    <button type="button" className="rounded px-1.5 py-0.5 text-[11px] font-bold text-[var(--bf-brand)] hover:bg-blue-50" onClick={() => { setEditingZoneId(Number(z.id)); setZoneFormOpen(true); }}>编辑</button>
                    <button type="button" className="rounded px-1.5 py-0.5 text-[11px] font-bold text-[#dc2626] hover:bg-red-50" onClick={() => { if (confirm(`删除分区「${text(z.zone_name)}」及其中所有书架？`)) deleteZoneMutation.mutate(Number(z.id)); }}>删除</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* shelf list */}
          {visibleShelfItems.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] font-black text-[#31405f]">书架列表</span>
                <button type="button" className="text-[11px] font-bold text-[var(--bf-brand)]" onClick={() => { setEditingShelfId(null); setShelfFormOpen(true); }}>＋ 新增</button>
              </div>
              <div className="space-y-1 flex-1 min-h-0 overflow-y-auto">
                {visibleShelfItems.map((s: AnyRecord) => (
                  <div key={String(s.id)} className="flex items-center justify-between rounded-lg border border-[#e8edf6] bg-white px-2.5 py-1.5">
                    <span className="text-[11px] font-bold text-[#101a35]">{text(s.shelf_code)}</span>
                    <span className="text-[10px] font-semibold text-[#94a3b8]">{text(s._zone_name || s.zone_name)}</span>
                    <div className="flex gap-0.5">
                      <button type="button" className="rounded px-1 py-0.5 text-[10px] font-bold text-[var(--bf-brand)] hover:bg-blue-50" onClick={() => { setEditingShelfId(Number(s.id)); setShelfFormOpen(true); }}>编辑</button>
                      <button type="button" className="rounded px-1 py-0.5 text-[10px] font-bold text-[#dc2626] hover:bg-red-50" onClick={() => { if (confirm(`删除书架「${text(s.shelf_code)}」？`)) deleteShelfMutation.mutate(Number(s.id)); }}>删除</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* dialogs */}
      <ZoneFormDialog open={zoneFormOpen} zoneId={editingZoneId} zones={zones} shelfCount={editingZoneId ? records(zones.find((z) => z.id === editingZoneId)?.shelves).length : 0} onClose={() => setZoneFormOpen(false)} onSaved={() => { setZoneFormOpen(false); invalidate(); }} />
      <ShelfFormDialog open={shelfFormOpen} shelfId={editingShelfId} activeFloor={activeFloor} zones={zones} allShelves={allShelves} onClose={() => setShelfFormOpen(false)} onSaved={() => { setShelfFormOpen(false); invalidate(); }} />
    </div>
  );
}

// ── Zone Form Dialog ──

function ZoneFormDialog({ open, zoneId, zones, shelfCount, onClose, onSaved }: { open: boolean; zoneId: number | null; zones: AnyRecord[]; shelfCount: number; onClose: () => void; onSaved: () => void }) {
  const existing = zoneId ? zones.find((z) => z.id === zoneId) : null;
  const colorIdx = zones.length % ZONE_COLORS.length;
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [floor, setFloor] = useState("");
  const [area, setArea] = useState(0);
  const [use, setUse] = useState("");
  const [color, setColor] = useState(ZONE_COLORS[colorIdx]);

  useEffect(() => {
    if (open) {
      setCode(text(existing?.zone_code));
      setName(text(existing?.zone_name));
      setFloor(text(existing?.floor));
      setArea(num(existing?.area_sqm));
      setUse(text(existing?.main_use));
      setColor(text(existing?.color, ZONE_COLORS[(zones.length) % ZONE_COLORS.length]));
    }
  }, [open, zoneId]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const offset = zones.length * 30;
      const body = zoneId
        ? { zone_code: code, zone_name: name, floor, area_sqm: area, main_use: use, color }
        : { zone_code: code, zone_name: name, floor, area_sqm: area, main_use: use, color, pos_x: 60 + offset, pos_y: 60 + offset, width: 200, height: 150 };
      return zoneId ? locationsApi.updateZone(zoneId, body) : locationsApi.createZone(body);
    },
    onSuccess: onSaved,
  });

  function handleSubmit(e: FormEvent) { e.preventDefault(); saveMutation.mutate(); }

  return (
    <FormDialog open={open} onOpenChange={(v) => { if (!v) onClose(); }} title={zoneId ? "编辑分区" : "新增分区"}>
      <form className="space-y-3" onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 gap-3">
          <input className={fieldClass()} placeholder="分区编号 *" value={code} onChange={(e) => setCode(e.target.value)} required disabled={!!zoneId} />
          <input className={fieldClass()} placeholder="分区名称 *" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <input className={fieldClass()} placeholder="楼层" value={floor} onChange={(e) => setFloor(e.target.value)} />
          <input className={fieldClass()} placeholder="面积（㎡）" type="number" value={area || ""} onChange={(e) => setArea(Number(e.target.value))} />
          <select className={fieldClass()} value={use} onChange={(e) => setUse(e.target.value)}>
            <option value="">用途</option>
            <option value="阅览区">阅览区</option>
            <option value="藏书区">藏书区</option>
            <option value="儿童区">儿童区</option>
            <option value="自习区">自习区</option>
            <option value="服务台">服务台</option>
            <option value="多功能区">多功能区</option>
          </select>
        </div>
        <div>
          <span className="text-[12px] font-bold text-[#64718d]">颜色</span>
          <div className="flex gap-2 mt-1">{ZONE_COLORS.map((c) => <button key={c} type="button" className={`h-8 w-8 rounded-full border-2 transition ${color === c ? "border-[#3b82f6] scale-110" : "border-transparent"}`} style={{ backgroundColor: c }} onClick={() => setColor(c)} />)}</div>
        </div>
        {zoneId ? <p className="text-[12px] font-semibold text-[var(--bf-text-secondary)]">当前含有 {shelfCount} 组书架</p> : null}
        <div className="flex justify-end gap-3 pt-2">
          <ActionButton variant="secondary" onClick={onClose}>取消</ActionButton>
          <ActionButton type="submit" icon="check" disabled={saveMutation.isPending}>{saveMutation.isPending ? "保存中" : "保存"}</ActionButton>
        </div>
      </form>
    </FormDialog>
  );
}

// ── Shelf Form Dialog ──

function ShelfFormDialog({ open, shelfId, activeFloor, zones, allShelves, onClose, onSaved }: { open: boolean; shelfId: number | null; activeFloor: string; zones: AnyRecord[]; allShelves: AnyRecord[]; onClose: () => void; onSaved: () => void }) {
  const existing = shelfId ? allShelves.find((s: AnyRecord) => s.id === shelfId) : null;
  const [code, setCode] = useState("");
  const [zoneId, setZoneId] = useState(0);
  const [index, setIndex] = useState(0);
  const [layers, setLayers] = useState(4);
  const [shelfType, setShelfType] = useState("formal");

  useEffect(() => {
    if (open) {
      setCode(text(existing?.shelf_code));
      const floorZones = zones.filter((z) => text(z.floor, "F1") === activeFloor);
      const fallbackZoneId = num(floorZones[0]?.id ?? zones[0]?.id);
      const targetZoneId = num(existing?.zone_id, fallbackZoneId);
      setZoneId(targetZoneId);
      setIndex(num(existing?.shelf_index, allShelves.filter((s: AnyRecord) => num(s.zone_id) === targetZoneId).length + 1));
      setLayers(num(existing?.layer_count, 4));
      setShelfType(text(existing?.shelf_type, "formal"));
    }
  }, [open, shelfId]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const zone = zones.find((item) => Number(item.id) === Number(zoneId));
      const zoneShelfCount = allShelves.filter((s: AnyRecord) => Number(s.zone_id) === Number(zoneId)).length;
      const body = {
        shelf_code: code,
        zone_id: zoneId,
        shelf_index: index,
        layer_count: layers,
        shelf_type: shelfType,
        pos_x: shelfId ? undefined : num(zone?.pos_x) + 26 + (zoneShelfCount % 4) * 64,
        pos_y: shelfId ? undefined : num(zone?.pos_y) + 46 + Math.floor(zoneShelfCount / 4) * 28,
        width: 54,
        height: 18,
      };
      return shelfId ? locationsApi.updateShelf(shelfId, body) : locationsApi.createShelf(body);
    },
    onSuccess: onSaved,
  });

  function handleSubmit(e: FormEvent) { e.preventDefault(); saveMutation.mutate(); }

  return (
    <FormDialog open={open} onOpenChange={(v) => { if (!v) onClose(); }} title={shelfId ? "编辑书架" : "新增书架"}>
      <form className="space-y-3" onSubmit={handleSubmit}>
        <select className={fieldClass()} value={zoneId} onChange={(e) => setZoneId(Number(e.target.value))} required>
          <option value={0}>所属分区 *</option>
          {zones.filter((z) => text(z.floor, "F1") === activeFloor).map((z) => <option key={String(z.id)} value={Number(z.id)}>{text(z.zone_name)} ({text(z.zone_code)})</option>)}
        </select>
        <div className="grid grid-cols-2 gap-3">
          <input className={fieldClass()} placeholder="书架编号 *" value={code} onChange={(e) => setCode(e.target.value)} required disabled={!!shelfId} />
          <input className={fieldClass()} placeholder="排序序号" type="number" value={index || ""} onChange={(e) => setIndex(Number(e.target.value))} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input className={fieldClass()} placeholder="层数" type="number" value={layers || ""} onChange={(e) => setLayers(Number(e.target.value))} />
          <select className={fieldClass()} value={shelfType} onChange={(e) => setShelfType(e.target.value)}>
            <option value="formal">正式馆藏</option>
            <option value="reservation">预约暂存</option>
            <option value="turnover">后台周转</option>
          </select>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <ActionButton variant="secondary" onClick={onClose}>取消</ActionButton>
          <ActionButton type="submit" icon="check" disabled={saveMutation.isPending}>{saveMutation.isPending ? "保存中" : "保存"}</ActionButton>
        </div>
      </form>
    </FormDialog>
  );
}
