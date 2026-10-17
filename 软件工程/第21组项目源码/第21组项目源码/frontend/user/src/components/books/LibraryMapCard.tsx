import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, X } from "lucide-react";
import { EmptyState } from "@/components/common/EmptyState";
import { bookApi } from "@/services/bookApi";
import type { BookCopy, BookItem } from "@/types/book";

type LibraryMapCardProps = {
  book?: BookItem | null;
  copies?: BookCopy[];
  selectedCopy?: BookCopy | null;
  initialFloor?: string;
  onSelectCopy?: (copy: BookCopy) => void;
};

type LayoutShelf = Record<string, unknown>;
type LayoutZone = Record<string, unknown> & { shelves?: LayoutShelf[] };

function normalizeFloor(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw.toUpperCase().startsWith("F") ? raw.toUpperCase() : `F${raw}`;
}

function sideFromPosition(positionCode?: string | null) {
  if (!positionCode) return "";
  const last = positionCode.split("-").pop() || "";
  if (["左", "右", "L", "R", "left", "right"].includes(last)) return last;
  return "";
}

function copyLocation(copy?: BookCopy | null) {
  if (!copy) return "暂无副本位置";
  const loc = copy.location;
  const floor = normalizeFloor(loc?.floor);
  const zone = [loc?.zone_code, loc?.zone_name].filter(Boolean).join("");
  const shelf = loc?.shelf_code;
  const side = sideFromPosition(loc?.position_code || loc?.shelf_position);
  const parts = [floor, zone, shelf].filter(Boolean);
  if (!parts.length) return "暂无副本位置";
  let result = parts.join("-");
  if (side) result += `-${side}`;
  return result;
}

function normalizedFloor(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw.toUpperCase().startsWith("F") ? raw.toUpperCase() : `F${raw}`;
}

function compactCode(value: unknown) {
  return String(value ?? "")
    .trim()
    .toUpperCase()
    .replace(/[\s_-]/g, "");
}

function stripFloorSuffix(value: string) {
  return value.replace(/F\d+$/i, "");
}

function sameCode(left: unknown, right: unknown) {
  const a = compactCode(left);
  const b = compactCode(right);
  if (!a || !b) return false;
  return a === b || stripFloorSuffix(a) === stripFloorSuffix(b);
}

function sameId(left: unknown, right: unknown) {
  if (left === null || left === undefined || right === null || right === undefined) return false;
  return String(left) === String(right);
}

function num(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function text(value: unknown, fallback = "") {
  return String(value ?? fallback).trim() || fallback;
}

function copyStatus(copy: BookCopy) {
  const status = text(copy.copy_status || copy.status);
  const labels: Record<string, string> = {
    available: "可借",
    borrowed: "已借出",
    reserved: "预约保留",
    maintenance: "维护中",
    unavailable: "暂不可借",
  };
  return labels[status] || status || "状态未知";
}

function zoneMatches(zone: LayoutZone, zoneCode?: string | null, zoneName?: string | null) {
  const expectedName = text(zoneName);
  return sameCode(zone.zone_code, zoneCode) || Boolean(expectedName && text(zone.zone_name) === expectedName);
}

function shelfMatches(shelf: LayoutShelf, copy?: BookCopy | null) {
  const location = copy?.location;
  return sameId(shelf.id, location?.shelf_id) || sameId(shelf.shelf_id, location?.shelf_id) || sameCode(shelf.shelf_code, location?.shelf_code);
}

function zoneTitle(zone: LayoutZone) {
  return ["区域", text(zone.zone_name), text(zone.zone_code)].filter(Boolean).join(" · ");
}

function shelfTitle(zone: LayoutZone, shelf: LayoutShelf) {
  return [zoneTitle(zone), `书架 ${text(shelf.shelf_code, "未编号")}`].filter(Boolean).join(" · ");
}

export function LibraryMapCard({ book, copies = [], selectedCopy, initialFloor = "", onSelectCopy }: LibraryMapCardProps) {
  const [mapOpen, setMapOpen] = useState(false);
  const [browseFloor, setBrowseFloor] = useState("");
  const layout = useQuery({ queryKey: ["reader", "locations", "tree"], queryFn: bookApi.getLocationTree, staleTime: 60_000 });
  const zones = (layout.data?.items ?? []) as LayoutZone[];
  const floors = useMemo(() => {
    const values = zones.map((item) => normalizedFloor(item.floor)).filter(Boolean);
    return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true }));
  }, [zones]);
  const activeCopy = selectedCopy ?? null;
  const activeCopyFloor = normalizedFloor(activeCopy?.location?.floor);
  const fallbackFloor = normalizedFloor(initialFloor) || floors[0] || "F1";
  const floor = activeCopyFloor || browseFloor || fallbackFloor;
  const zoneName = activeCopy?.location?.zone_name || null;
  const zoneCode = activeCopy?.location?.zone_code || null;
  const floorZones = zones.filter((item) => normalizedFloor(item.floor) === floor);
  const visibleZones = floorZones.length ? floorZones : zones.filter((item) => normalizedFloor(item.floor) === "F1");
  const matchedZone = activeCopy ? visibleZones.find((item) => zoneMatches(item, zoneCode, zoneName)) : null;
  const matchedShelf = activeCopy ? visibleZones.flatMap((item) => item.shelves ?? []).find((item) => shelfMatches(item, activeCopy)) : null;
  const copyOptions = copies;
  const hasSelectedCopy = Boolean(activeCopy);
  const viewBox = "0 0 1032 840";

  useEffect(() => {
    const next = normalizedFloor(initialFloor);
    if (next) setBrowseFloor(next);
  }, [initialFloor]);

  useEffect(() => {
    const next = normalizedFloor(selectedCopy?.location?.floor);
    if (next) setBrowseFloor(next);
  }, [selectedCopy?.id, selectedCopy?.location?.floor]);

  function renderMap(large = false) {
    if (layout.isError) {
      return <div className="library-map-card__empty"><EmptyState title="地图暂不可用" description="公开馆内地图接口暂未返回数据" /></div>;
    }
    if (layout.isLoading) return <div className="skeleton-row" />;
    if (!zones.length) {
      return <div className="library-map-card__empty"><EmptyState title="暂无地图数据" description="请先在系统设置中维护公开馆藏地图" /></div>;
    }
    return (
      <svg className={large ? "library-map-card__svg library-map-card__svg--large" : "library-map-card__svg"} viewBox={viewBox} role="img" aria-label={`${floor} 馆内地图`}>
        <rect className="library-map-card__shell" x="24" y="24" width="984" height="780" rx="8">
          <title>{`${floor} 馆内地图`}</title>
        </rect>
        {visibleZones.map((item) => {
          const active = Boolean(matchedZone && (sameId(item.id, matchedZone.id) || sameCode(item.zone_code, matchedZone.zone_code)));
          return (
            <g key={text(item.zone_code, String(item.id))}>
              <rect
                className={active ? "library-map-card__zone library-map-card__zone--active" : "library-map-card__zone"}
                fill={text(item.color, "#eef4ff")}
                height={num(item.height, 120)}
                rx="8"
                width={num(item.width, 160)}
                x={num(item.pos_x)}
                y={num(item.pos_y)}
              >
                <title>{zoneTitle(item)}</title>
              </rect>
              {(item.shelves ?? []).map((shelf) => {
                const shelfActive = Boolean(matchedShelf && (sameId(shelf.id, matchedShelf.id) || sameId(shelf.shelf_id, matchedShelf.shelf_id) || sameCode(shelf.shelf_code, matchedShelf.shelf_code)));
                return (
                  <rect
                    key={text(shelf.shelf_code, String(shelf.id))}
                    className={shelfActive ? "library-map-card__shelf library-map-card__shelf--active" : "library-map-card__shelf"}
                    height={num(shelf.height, 18)}
                    rx="3"
                    width={num(shelf.width, 54)}
                    x={num(shelf.pos_x)}
                    y={num(shelf.pos_y)}
                  >
                    <title>{shelfTitle(item, shelf)}</title>
                  </rect>
                );
              })}
            </g>
          );
        })}
      </svg>
    );
  }

  const mapDialog = mapOpen
    ? createPortal(
        <div className="reader-map-dialog" role="dialog" aria-modal="true" aria-label="馆内地图放大查看">
          <div className="reader-map-dialog__backdrop" onClick={() => setMapOpen(false)} />
          <div className="reader-map-dialog__panel">
            <div className="reader-map-dialog__header">
              <div>
                <strong>{activeCopy?.copy_code || `${floor} 馆内地图`}</strong>
                <span>{activeCopy ? copyLocation(activeCopy) : "可自由查看楼层；选中具体副本后高亮对应书架"}</span>
              </div>
              <button type="button" onClick={() => setMapOpen(false)} aria-label="关闭地图"><X size={20} /></button>
            </div>
            <div className="reader-map-dialog__body">{renderMap(true)}</div>
          </div>
        </div>,
        document.body,
      )
    : null;

  return (
    <div className="library-map-card">
      <div className="library-map-card__header">
        <div>
          <h2>馆藏位置</h2>
          <span>{activeCopy ? "已定位到具体副本" : book ? "请选择副本后高亮书架" : "可自由查看馆内楼层"}</span>
        </div>
        <button type="button" onClick={() => setMapOpen(true)}><Maximize2 size={15} />放大查看</button>
      </div>

      {floors.length > 1 ? (
        <div className="library-map-card__floor-tabs" aria-label="楼层切换">
          {floors.map((item) => (
            <button
              key={item}
              className={item === floor ? "is-active" : ""}
              type="button"
              onClick={() => setBrowseFloor(item)}
            >
              {item}
            </button>
          ))}
        </div>
      ) : null}

      <div className="library-map-card__map library-map-card__map--linked" aria-label="馆内定位示意图">
        {renderMap(false)}
      </div>

      {copyOptions.length ? (
        <div className="library-map-card__copy-list" aria-label="副本位置列表">
          {copyOptions.map((copy) => {
            const active = activeCopy?.id === copy.id;
            return (
              <button
                key={copy.id}
                className={active ? "library-map-card__copy-option library-map-card__copy-option--active" : "library-map-card__copy-option"}
                type="button"
                onClick={() => onSelectCopy?.(copy)}
              >
                <strong>{copy.copy_code || `副本 ${copy.id}`}</strong>
                <span>{copyLocation(copy)}</span>
                <em>{copyStatus(copy)}</em>
              </button>
            );
          })}
        </div>
      ) : book ? (
        <p className="library-map-card__copy-hint">这本书暂未返回可定位副本，可先浏览楼层地图。</p>
      ) : null}

      {!hasSelectedCopy && copyOptions.length ? (
        <p className="library-map-card__copy-hint">点选副本后，地图会高亮对应书架。</p>
      ) : null}
      {mapDialog}
    </div>
  );
}
