"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

interface AutoScrollOptions {
  hasMessages: boolean;
  isStreaming: boolean;
  composerHeight: number;
  messageCount: number;
  lastMessageContent?: string;
  lastEventCount?: number;
}

/** Follow layout changes until the reader intentionally leaves the live end.
 * Observe content size, not an arbitrary post-stream timeout: markdown, images
 * and disclosure animations can settle independently of the transport.
 * The scroll root must retain overflow-anchor: none to avoid competing writers.
 */
export function useChatAutoScroll({
  hasMessages, isStreaming, composerHeight, messageCount,
  lastMessageContent, lastEventCount,
}: AutoScrollOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const positionRef = useRef({ top: 0, height: 0, viewport: 0 });
  // Whether the live end is on screen. This is state only so chrome such as the
  // chat's back-to-bottom control can react to it; the ref takes the value on
  // every scroll event, so the component re-renders on threshold crossings, not
  // per frame.
  const [isAtBottom, setIsAtBottom] = useState(true);
  const atBottomRef = useRef(true);

  const syncAtBottom = useCallback((container: HTMLDivElement) => {
    const next =
      container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    if (next === atBottomRef.current) return;
    atBottomRef.current = next;
    setIsAtBottom(next);
  }, []);

  const rememberPosition = useCallback((container: HTMLDivElement) => {
    positionRef.current = {
      top: container.scrollTop,
      height: container.scrollHeight,
      viewport: container.clientHeight,
    };
  }, []);

  const pinToBottom = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
    rememberPosition(container);
    syncAtBottom(container);
  }, [rememberPosition, syncAtBottom]);

  useLayoutEffect(() => {
    if (hasMessages && shouldAutoScrollRef.current) {
      pinToBottom();
    } else if (containerRef.current) {
      // Loaded history opens wherever the reader left it; read the control's
      // state from that position instead of assuming the live end is visible.
      syncAtBottom(containerRef.current);
    }
  }, [pinToBottom, syncAtBottom, hasMessages, isStreaming, messageCount,
    lastMessageContent, lastEventCount, composerHeight]);

  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const previous = positionRef.current;
    // The browser clamps scrollTop when content shrinks. That is not a user
    // gesture. Growth never moves it (overflow-anchor: none), so whatever the
    // layout did, the position without the reader is at most the new maximum.
    // Comparing against that keeps a scrollbar drag during streaming, when the
    // reply grows between the drag and its scroll event, a gesture (#2072).
    const max = Math.max(0, container.scrollHeight - container.clientHeight);
    const expected = Math.min(previous.top, max);
    const remaining = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (remaining < 80 && (shouldAutoScrollRef.current || container.scrollTop > expected + 4)) {
      shouldAutoScrollRef.current = true;
    }
    else if (container.scrollTop < expected - 4) shouldAutoScrollRef.current = false;
    syncAtBottom(container);
    rememberPosition(container);
  }, [rememberPosition, syncAtBottom]);

  useEffect(() => {
    if (!hasMessages) return;
    const container = containerRef.current;
    if (!container) return;
    let rafId = 0;
    const schedule = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        rafId = 0;
        if (shouldAutoScrollRef.current) {
          pinToBottom();
        } else {
          rememberPosition(container);
          syncAtBottom(container);
        }
      });
    };
    // A scrollport's own box does not grow with scrollHeight. Observe its
    // content children too: main chat has a wrapper, PartnerChat has rows.
    const observed = new Set<Element>();
    const resize = new ResizeObserver(schedule);
    const observeContent = () => {
      const targets = new Set<Element>([container, ...container.children]);
      for (const target of observed) {
        if (!targets.has(target)) { resize.unobserve(target); observed.delete(target); }
      }
      for (const target of targets) {
        if (!observed.has(target)) { resize.observe(target); observed.add(target); }
      }
      schedule();
    };
    const mutations = new MutationObserver(observeContent);
    mutations.observe(container, { childList: true, subtree: true });
    container.addEventListener("load", schedule, true);
    observeContent();

    const release = () => { shouldAutoScrollRef.current = false; };
    const onWheel = (event: WheelEvent) => { if (event.deltaY < 0) release(); };
    let touchY = 0;
    const onTouchStart = (event: TouchEvent) => { touchY = event.touches[0]?.clientY ?? 0; };
    const onTouchMove = (event: TouchEvent) => {
      const y = event.touches[0]?.clientY ?? 0;
      if (y - touchY > 4) release();
      touchY = y;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest("input,textarea,[contenteditable='true']")) return;
      if (["ArrowUp", "PageUp", "Home"].includes(event.key) || (event.key === " " && event.shiftKey)) release();
    };
    const onPointerDown = (event: PointerEvent) => {
      // Opening a trace/citation is deliberate browsing, not late model output.
      // Sending/answering re-arms follow at the existing caller-owned boundary.
      const target = event.target;
      if (target instanceof Element && target.closest("button,a,summary,[role='button']")) release();
    };
    container.addEventListener("wheel", onWheel, { passive: true });
    container.addEventListener("touchstart", onTouchStart, { passive: true });
    container.addEventListener("touchmove", onTouchMove, { passive: true });
    container.addEventListener("keydown", onKeyDown);
    container.addEventListener("pointerdown", onPointerDown, true);
    return () => {
      resize.disconnect(); mutations.disconnect();
      container.removeEventListener("load", schedule, true);
      container.removeEventListener("wheel", onWheel);
      container.removeEventListener("touchstart", onTouchStart);
      container.removeEventListener("touchmove", onTouchMove);
      container.removeEventListener("keydown", onKeyDown);
      container.removeEventListener("pointerdown", onPointerDown, true);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [hasMessages, pinToBottom, rememberPosition, syncAtBottom]);

  const scrollToBottom = useCallback((_behavior: ScrollBehavior) => {
    void _behavior;
    pinToBottom();
  }, [pinToBottom]);

  return {
    containerRef,
    endRef,
    shouldAutoScrollRef,
    isAtBottom,
    scrollToBottom,
    handleScroll,
  };
}
