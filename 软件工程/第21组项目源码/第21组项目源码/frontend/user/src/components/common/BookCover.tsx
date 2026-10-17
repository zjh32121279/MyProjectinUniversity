import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { BookOpen, X } from "lucide-react";

type BookCoverProps = {
  src?: string | null;
  title?: string | null;
  compact?: boolean;
};

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
    <div className="book-cover-lightbox" role="dialog" aria-modal="true" aria-label="封面大图预览" onClick={onClose}>
      <button
        className="book-cover-lightbox__close"
        type="button"
        aria-label="关闭封面预览"
        onClick={(event) => {
          event.stopPropagation();
          onClose();
        }}
      >
        <X size={22} />
      </button>
      <img
        className="book-cover-lightbox__image"
        src={src}
        alt={label}
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

export function BookCover({ src, title, compact = false }: BookCoverProps) {
  const [failed, setFailed] = useState(false);
  const [zoomOpen, setZoomOpen] = useState(false);
  const cleanSrc = String(src ?? "").trim();
  const label = title || "图书封面";

  useEffect(() => {
    setFailed(false);
    setZoomOpen(false);
  }, [cleanSrc]);

  if (cleanSrc && !failed) {
    return (
      <>
        <img
          className={compact ? "book-cover book-cover--compact book-cover--image" : "book-cover book-cover--image"}
          src={cleanSrc}
          alt={label}
          loading="lazy"
          referrerPolicy="no-referrer"
          draggable={false}
          onError={() => {
            setFailed(true);
            setZoomOpen(false);
          }}
          onDoubleClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setZoomOpen(true);
          }}
          title="双击放大封面"
        />
        {zoomOpen ? <CoverLightbox src={cleanSrc} label={label} onClose={() => setZoomOpen(false)} /> : null}
      </>
    );
  }
  return (
    <div className={compact ? "book-cover book-cover--compact book-cover--empty" : "book-cover book-cover--empty"}>
      <BookOpen size={compact ? 20 : 30} />
      <span>暂无封面</span>
    </div>
  );
}
