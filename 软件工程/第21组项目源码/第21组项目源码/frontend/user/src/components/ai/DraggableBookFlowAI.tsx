import { useEffect, useRef, useState, type PointerEvent } from "react";
import { BookFlowAIWidget } from "@/components/ai/BookFlowAIWidget";

const STORAGE_KEY = "bookflow:user:ai-widget-position";
const SAFE = 16;
const TOP_SAFE = 80;
const DEFAULT_WIDTH = 176;
const DEFAULT_HEIGHT = 54;

type Position = {
  x: number;
  y: number;
};

function clampPosition(pos: Position, width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT): Position {
  const maxX = Math.max(SAFE, window.innerWidth - width - SAFE);
  const maxY = Math.max(TOP_SAFE, window.innerHeight - height - SAFE);
  return {
    x: Math.min(Math.max(SAFE, pos.x), maxX),
    y: Math.min(Math.max(TOP_SAFE, pos.y), maxY),
  };
}

function defaultPosition(): Position {
  return clampPosition({ x: window.innerWidth - DEFAULT_WIDTH - 24, y: window.innerHeight - DEFAULT_HEIGHT - 24 });
}

export function DraggableBookFlowAI() {
  const ref = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; originX: number; originY: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);
  const [position, setPosition] = useState<Position>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPosition();
    try {
      return clampPosition(JSON.parse(raw) as Position);
    } catch {
      return defaultPosition();
    }
  });
  const [expanded, setExpanded] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    function handleResize() {
      const rect = ref.current?.getBoundingClientRect();
      setPosition((current) => clampPosition(current, rect?.width, rect?.height));
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(position));
  }, [position]);

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    if (target.closest(".ai-widget__panel")) return;
    dragRef.current = { startX: event.clientX, startY: event.clientY, originX: position.x, originY: position.y, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    const dx = event.clientX - dragRef.current.startX;
    const dy = event.clientY - dragRef.current.startY;
    if (Math.abs(dx) + Math.abs(dy) > 4) {
      dragRef.current.moved = true;
      setDragging(true);
    }
    const rect = ref.current?.getBoundingClientRect();
    setPosition(clampPosition({ x: dragRef.current.originX + dx, y: dragRef.current.originY + dy }, rect?.width, rect?.height));
  }

  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) return;
    const moved = dragRef.current.moved;
    dragRef.current = null;
    setDragging(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
    suppressClickRef.current = true;
    if (!moved) {
      setExpanded((current) => !current);
    }
    window.setTimeout(() => {
      suppressClickRef.current = false;
    }, 0);
  }

  function togglePanel() {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    setExpanded((current) => !current);
  }

  return (
    <div
      ref={ref}
      className="ai-draggable"
      style={{ transform: `translate3d(${position.x}px, ${position.y}px, 0)` }}
      onPointerDown={pointerDown}
      onPointerMove={pointerMove}
      onPointerUp={pointerUp}
    >
      <BookFlowAIWidget expanded={expanded} onToggle={togglePanel} onCollapse={() => setExpanded(false)} dragging={dragging} />
    </div>
  );
}
