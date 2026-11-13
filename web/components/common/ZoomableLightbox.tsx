"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { X, ZoomIn, ZoomOut } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * Full-screen viewer for diagrams and page images.
 *
 * The chat container is narrow, so a wide diagram or a scanned page is either
 * shrunk to unreadable or clipped. This overlay gives the content the whole
 * viewport plus explicit zoom stops. The content auto-fits once (stopping at
 * minScale so text keeps a readable size) and then follows the zoom buttons.
 */
export default function ZoomableLightbox({
  open,
  onClose,
  title,
  minScale = 0.2,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  /** Auto-fit never goes below this, so text stays legible instead of shrinking to fit. */
  minScale?: number;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const viewportRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const touchedRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    touchedRef.current = false;
    setScale(1);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  // Fit once the content has a real size. Images load asynchronously, so keep
  // probing for a few seconds and take the first measurement that is non-zero.
  useEffect(() => {
    if (!open) return;
    let raf = 0;
    const startedAt = performance.now();
    const tick = () => {
      const viewport = viewportRef.current;
      const content = contentRef.current;
      if (viewport && content && !touchedRef.current) {
        const width = content.scrollWidth;
        const height = content.scrollHeight;
        if (width > 0 && height > 0) {
          const fit = Math.min(
            1,
            (viewport.clientWidth - 32) / width,
            (viewport.clientHeight - 32) / height,
          );
          const next = Math.max(minScale, fit);
          if (Number.isFinite(next) && next > 0) setScale(next);
          return;
        }
      }
      if (performance.now() - startedAt < 5000) {
        raf = requestAnimationFrame(tick);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [open, minScale]);

  const zoomBy = useCallback((factor: number) => {
    touchedRef.current = true;
    setScale((current) => Math.min(8, Math.max(0.1, current * factor)));
  }, []);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title || t("Fullscreen")}
      className="fixed inset-0 z-[300] flex flex-col bg-[var(--overlay,#000)]/90 backdrop-blur-sm"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="flex shrink-0 items-center gap-2 border-b border-white/10 px-3 py-2 text-[var(--card-foreground,#fff)]">
        {title ? (
          <span className="min-w-0 flex-1 truncate text-xs opacity-80">{title}</span>
        ) : (
          <span className="flex-1" />
        )}
        <button
          type="button"
          onClick={() => zoomBy(1 / 1.25)}
          title={t("Zoom out")}
          aria-label={t("Zoom out")}
          className="rounded-md p-1.5 hover:bg-white/10"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <span className="w-12 text-center text-xs tabular-nums opacity-80">
          {Math.round(scale * 100)}%
        </span>
        <button
          type="button"
          onClick={() => zoomBy(1.25)}
          title={t("Zoom in")}
          aria-label={t("Zoom in")}
          className="rounded-md p-1.5 hover:bg-white/10"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onClose}
          title={t("Close")}
          aria-label={t("Close")}
          className="rounded-md p-1.5 hover:bg-white/10"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div
        ref={viewportRef}
        className="min-h-0 flex-1 overflow-auto"
        onClick={(event) => {
          if (event.target === event.currentTarget) onClose();
        }}
      >
        <div className="mx-auto flex w-max min-w-full items-start justify-center p-4">
          <div
            ref={contentRef}
            style={{ zoom: scale }}
            className="bg-[var(--card,#fff)]"
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
