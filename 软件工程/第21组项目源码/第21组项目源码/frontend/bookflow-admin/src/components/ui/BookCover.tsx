import { useEffect, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/utils/cn";
import { BookPlaceholder } from "@/components/ui/BookPlaceholder";

type BookCoverProps = {
  title?: string;
  code?: string;
  categoryCode?: string;
  coverUrl?: string | null;
  size?: "sm" | "lg";
  className?: string;
};

function cleanUrl(value?: string | null) {
  return String(value ?? "").trim();
}

function CoverLightbox({ src, label, onClose }: { src: string; label: string; onClose: () => void }) {
  useEffect(() => {
    if (typeof document === "undefined") return;
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-[#0f172a]/75 p-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="封面大图预览"
      onClick={onClose}
    >
      <button
        type="button"
        className="absolute right-5 top-5 inline-flex h-11 w-11 items-center justify-center rounded-full border border-white/25 bg-white/95 text-[#0f172a] shadow-lg transition hover:bg-white"
        aria-label="关闭封面预览"
        onClick={(event) => {
          event.stopPropagation();
          onClose();
        }}
      >
        <X size={22} />
      </button>
      <img
        src={src}
        alt={label}
        className="max-h-[88vh] max-w-[88vw] cursor-zoom-out rounded-[18px] bg-white object-contain shadow-[0_28px_90px_rgba(0,0,0,0.42)]"
        draggable={false}
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => {
          event.stopPropagation();
          onClose();
        }}
      />
    </div>,
    document.body,
  );
}

export function BookCover({ title, code, categoryCode, coverUrl, size = "sm", className }: BookCoverProps) {
  const [failed, setFailed] = useState(false);
  const [zoomOpen, setZoomOpen] = useState(false);
  const src = cleanUrl(coverUrl);
  const large = size === "lg";
  const label = title || code || "图书封面";

  useEffect(() => {
    setFailed(false);
    setZoomOpen(false);
  }, [src]);

  if (src && !failed) {
    return (
      <>
        <div
          className={cn(large ? "h-[86px] w-[62px] rounded-2xl" : "h-14 w-10 rounded-lg", "shrink-0 overflow-hidden border border-[#dfe7f4] bg-[#f7f9fd] shadow-sm", className)}
          onClick={(event: MouseEvent<HTMLDivElement>) => event.stopPropagation()}
          onDoubleClick={(event: MouseEvent<HTMLDivElement>) => {
            event.preventDefault();
            event.stopPropagation();
            setZoomOpen(true);
          }}
        >
          <img
            src={src}
            alt={label}
            className="h-full w-full cursor-zoom-in object-cover"
            loading="lazy"
            referrerPolicy="no-referrer"
            draggable={false}
            onError={() => {
              setFailed(true);
              setZoomOpen(false);
            }}
          />
        </div>
        {zoomOpen ? <CoverLightbox src={src} label={label} onClose={() => setZoomOpen(false)} /> : null}
      </>
    );
  }

  return <BookPlaceholder title={title} code={code} categoryCode={categoryCode} size={size} className={className} />;
}
