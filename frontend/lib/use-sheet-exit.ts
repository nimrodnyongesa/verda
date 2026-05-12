"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * useSheetExit — give a modal / sheet a smooth exit animation.
 *
 * Modals in this codebase unmount immediately when their parent sets
 * the `open` flag to false; that gives no time for an exit animation.
 * This hook wraps the real close callback in a 220 ms delay during
 * which a `closing` flag is true. Wire `data-state={closing ? "closing"
 * : "open"}` onto the sheet panel and on the backdrop overlay; the
 * matching CSS in `globals.css` then plays the slide-down (mobile) or
 * fade-out (desktop) animation before the element is removed from the
 * DOM.
 *
 * Returns:
 *   * ``closing`` — boolean, set to true the moment ``trigger`` fires.
 *   * ``trigger`` — wrap any caller that wants to dismiss the modal.
 *
 * The duration matches the longer of the two animation pairs in the
 * stylesheet, so the unmount lands after the visual is fully off-screen.
 */
export function useSheetExit(
  realClose: () => void,
  durationMs = 220
): { closing: boolean; trigger: () => void } {
  const [closing, setClosing] = useState(false);
  const cb = useRef(realClose);
  cb.current = realClose;
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current != null) window.clearTimeout(timer.current);
    },
    []
  );

  const trigger = useCallback(() => {
    if (closing) return;
    setClosing(true);
    timer.current = window.setTimeout(() => {
      cb.current();
    }, durationMs);
  }, [closing, durationMs]);

  return { closing, trigger };
}
