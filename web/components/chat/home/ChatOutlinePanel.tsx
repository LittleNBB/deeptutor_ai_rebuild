"use client";

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { useTranslation } from "react-i18next";
import { ListOrdered, X } from "lucide-react";

import type { ChatOutlineEntry } from "@/lib/chat-outline";

/** The line below the top fade that counts as "the reader is here". */
const ACTIVE_LINE_PX = 140;
const SCROLL_PAD_PX = 8;

interface ChatOutlinePanelProps {
  entries: ChatOutlineEntry[];
  scrollRootRef: RefObject<HTMLDivElement | null>;
  onJump: (entry: ChatOutlineEntry) => void;
  onClose: () => void;
  /**
   * Surfaces whose transcript sits beside other columns keep the panel overlaid
   * at every width (there is no spare gutter to dock it into).
   */
  overlay?: boolean;
}

/**
 * The conversation's questions as a list, docked beside the transcript on wide
 * screens and overlaid on narrow ones. Clicking a row jumps to that turn; the
 * row at the reader's current position stays highlighted while scrolling, and
 * the list follows it.
 */
export function ChatOutlinePanel({
  entries,
  scrollRootRef,
  onJump,
  onClose,
  overlay = false,
}: ChatOutlinePanelProps) {
  const { t } = useTranslation();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const activeRef = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = scrollRootRef.current;
    if (!root) return;
    let frame = 0;
    const compute = () => {
      frame = 0;
      const line = root.getBoundingClientRect().top + ACTIVE_LINE_PX;
      const nodes = new Map<string, HTMLElement>();
      root.querySelectorAll<HTMLElement>("[data-turn-key]").forEach((node) => {
        const key = node.dataset.turnKey;
        if (key && !nodes.has(key)) nodes.set(key, node);
      });
      let next: string | null = null;
      for (const entry of entries) {
        const node = nodes.get(entry.key);
        if (!node) continue;
        if (node.getBoundingClientRect().top <= line) next = entry.key;
        else break;
      }
      if (!next && entries.length > 0) next = entries[0].key;
      if (next === activeRef.current) return;
      activeRef.current = next;
      setActiveKey(next);
    };
    const schedule = () => {
      if (frame) return;
      frame = requestAnimationFrame(compute);
    };
    compute();
    root.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      root.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [entries, scrollRootRef]);

  useEffect(() => {
    const list = listRef.current;
    if (!list || !activeKey) return;
    const rows = list.querySelectorAll<HTMLElement>("[data-outline-key]");
    const row = Array.from(rows).find(
      (el) => el.dataset.outlineKey === activeKey,
    );
    if (!row) return;
    const top = row.offsetTop;
    const bottom = top + row.offsetHeight;
    if (top < list.scrollTop + SCROLL_PAD_PX) {
      list.scrollTop = Math.max(0, top - SCROLL_PAD_PX);
    } else if (bottom > list.scrollTop + list.clientHeight - SCROLL_PAD_PX) {
      list.scrollTop = bottom - list.clientHeight + SCROLL_PAD_PX;
    }
  }, [activeKey]);

  return (
    <aside
      data-outline-panel="true"
      aria-label={t("Conversation outline")}
      className={
        "absolute inset-y-0 right-0 z-30 flex w-[288px] shrink-0 flex-col border-l border-[var(--border)] bg-[var(--background)] shadow-xl " +
        (overlay ? "" : "xl:static xl:z-auto xl:shadow-none")
      }
    >
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)]/70 px-3.5 py-2.5">
        <span className="flex min-w-0 items-center gap-1.5 text-[12.5px] font-medium text-[var(--foreground)]">
          <ListOrdered
            size={13}
            strokeWidth={1.8}
            aria-hidden="true"
            className="shrink-0 text-[var(--muted-foreground)]"
          />
          <span className="truncate">{t("Conversation outline")}</span>
          <span className="shrink-0 rounded-full bg-[var(--muted)] px-1.5 py-0.5 text-[10px] tabular-nums text-[var(--muted-foreground)]">
            {entries.length}
          </span>
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("Close")}
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[var(--muted-foreground)] transition hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
        >
          <X size={13} strokeWidth={1.8} />
        </button>
      </header>
      <div
        ref={listRef}
        className="relative min-h-0 flex-1 overflow-y-auto px-1.5 py-2 [scrollbar-width:thin]"
      >
        {entries.length === 0 ? (
          <p className="px-3 py-6 text-center text-[11.5px] leading-relaxed text-[var(--muted-foreground)]">
            {t("No questions yet")}
          </p>
        ) : (
          <ol className="space-y-0.5">
            {entries.map((entry) => {
              const active = entry.key === activeKey;
              return (
                <li key={entry.key}>
                  <button
                    type="button"
                    data-outline-key={entry.key}
                    onClick={() => onJump(entry)}
                    aria-current={active ? "true" : undefined}
                    title={entry.title}
                    className={
                      "group flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors " +
                      (active
                        ? "bg-[var(--muted)]"
                        : "hover:bg-[var(--muted)]/55")
                    }
                  >
                    <span
                      className={
                        "mt-px w-4 shrink-0 text-right text-[10.5px] tabular-nums " +
                        (active
                          ? "text-[var(--foreground)]"
                          : "text-[var(--muted-foreground)]")
                      }
                    >
                      {entry.ordinal}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 block text-[12px] leading-[1.4] text-[var(--foreground)]">
                        {entry.title}
                      </span>
                      {entry.reply ? (
                        <span className="mt-0.5 block truncate text-[10.5px] leading-[1.4] text-[var(--muted-foreground)]">
                          {entry.reply}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </aside>
  );
}
