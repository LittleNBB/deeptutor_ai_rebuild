"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { StreamEvent } from "@/features/chat/model/protocol";
import { apiUrl } from "@/lib/api";
import ImagePreview from "@/components/chat/preview/previewers/ImagePreview";
import { useBinarySource } from "@/components/chat/preview/previewers/useBinarySource";
import { presentedPagesFromSources, type PresentedPage } from "@/lib/mastery-source-pages";

type Page = PresentedPage;

function presentedPages(events: StreamEvent[], placed: ReadonlySet<string>): Page[] {
  const pages = new Map<string, Page>();
  for (const event of events) {
    if (event.type !== "sources" || !["chat", "mastery_path"].includes(event.source)) continue;
    for (const page of presentedPagesFromSources(event.metadata.sources)) {
      // A page already shown at its tool call is not stacked again below.
      if (!placed.has(page.preview_url)) pages.set(page.preview_url, page);
    }
  }
  return [...pages.values()].slice(0, 12);
}

/** The page image itself, mounted only while the disclosure is open. */
function SourcePageImage({ page }: { page: Page }) {
  const { t } = useTranslation();
  const state = useBinarySource(apiUrl(page.preview_url), "image/png");
  const url = state.kind === "ready" ? state.objectUrl : null;
  return url ? (
    <div className="h-[min(72vh,760px)] w-full">
      <ImagePreview url={url} filename={page.title} />
    </div>
  ) : (
    <p role="status" className="p-2 text-sm">
      {state.kind === "error" ? t("Failed to load image.") : t("Loading...")}
    </p>
  );
}

/**
 * A source page stays a one-line receipt until the learner asks for it.
 *
 * These pages are full textbook scans: opened by default, two of them push the
 * prose off the screen and the answer reads as a gallery. The summary names the
 * page, the image is fetched only when expanded, and the expanded image keeps
 * its own click-to-zoom preview.
 */
function SourcePage({ page }: { page: Page }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="group my-3 rounded-lg border border-[var(--border)]"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 p-2 text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)] [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={14}
          className="shrink-0 transition-transform group-open:rotate-90"
          aria-hidden
        />
        <span className="break-words">{page.title}</span>
      </summary>
      {open ? (
        <div className="px-2 pb-2">
          <SourcePageImage page={page} />
        </div>
      ) : null}
    </details>
  );
}

/** Render publication receipts; publication does not prove that a learner viewed a page. */
export function MasterySourcePresentation({ events, placed }: {
  events: StreamEvent[];
  /** Preview URLs already rendered where their tool call happened. */
  placed?: ReadonlySet<string>;
}) {
  return <>{presentedPages(events, placed ?? NONE).map(page => <SourcePage key={page.preview_url} page={page} />)}</>;
}

const NONE: ReadonlySet<string> = new Set();

/** The pages one tool call presented, shown where that call happened. */
export function MasterySourcePages({ pages }: { pages: PresentedPage[] }) {
  return <>{pages.map(page => <SourcePage key={page.preview_url} page={page} />)}</>;
}
