"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  close,
  subscribe,
  type DialogRequest,
  type DialogVariant,
} from "@/lib/dialog";
import { useSheetExit } from "@/lib/use-sheet-exit";

const TONE: Record<DialogVariant, { bar: string; chip: string; cta: string }> = {
  info: {
    bar: "bg-ink",
    chip: "bg-ink/10 text-ink border-ink/20",
    cta: "bg-ink text-paper hover:bg-ink-soft border-ink",
  },
  success: {
    bar: "bg-fern",
    chip: "bg-fern/15 text-fern border-fern/30",
    cta: "bg-fern text-paper hover:bg-fern/85 border-fern",
  },
  warning: {
    bar: "bg-gold",
    chip: "bg-gold-soft/70 text-ink border-gold/40",
    cta: "bg-gold text-ink hover:bg-gold-bright border-gold",
  },
  danger: {
    bar: "bg-rust",
    chip: "bg-rust/15 text-rust border-rust/30",
    cta: "bg-rust text-paper hover:bg-rust/85 border-rust",
  },
};

const ICON: Record<DialogVariant, string> = {
  info: "ℹ",
  success: "✓",
  warning: "!",
  danger: "!",
};

export function DialogHost() {
  const [queue, setQueue] = useState<DialogRequest[]>([]);
  useEffect(() => subscribe(setQueue), []);

  // Lock body scroll while a dialog is open.
  useEffect(() => {
    if (!queue.length) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [queue.length]);

  // Render only the head of the queue (one dialog at a time).
  const current = queue[0] ?? null;
  if (!current) return null;
  return <DialogShell key={current.id} request={current} />;
}

function DialogShell({ request }: { request: DialogRequest }) {
  const variant: DialogVariant =
    request.kind === "confirm" || request.kind === "prompt" || request.kind === "alert"
      ? request.options.variant ?? (request.kind === "confirm" ? "warning" : "info")
      : "info";
  const tone = TONE[variant];
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const firstFocusableRef = useRef<HTMLButtonElement | HTMLInputElement | null>(null);
  const lastActiveRef = useRef<HTMLElement | null>(null);
  // Exit animation — `closing` flips true 220 ms before the host actually
  // unmounts the dialog from the queue, giving the slide-down (mobile) /
  // fade-out (desktop) animation room to play.
  const { closing, trigger: animatedDismiss } = useSheetExit(
    () => close(request.id),
    220
  );

  // Focus management — capture, trap, restore.
  useEffect(() => {
    lastActiveRef.current = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => firstFocusableRef.current?.focus(), 0);
    return () => {
      clearTimeout(t);
      lastActiveRef.current?.focus?.();
    };
  }, []);

  // Esc closes (cancels confirm/prompt; resolves alert).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        cancel();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(
            'a,button,input,select,textarea,[tabindex]:not([tabindex="-1"])'
          )
        ).filter((el) => !el.hasAttribute("disabled"));
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function cancel() {
    if (request.kind === "confirm") request.resolve(false);
    else if (request.kind === "prompt") request.resolve(null);
    else request.resolve();
    animatedDismiss();
  }

  return (
    <div
      role="presentation"
      data-overlay
      data-state={closing ? "closing" : "open"}
      onClick={(e) => {
        if (e.target === e.currentTarget) cancel();
      }}
      className="fixed inset-0 z-[200] flex items-end justify-center bg-ink/55 px-4 pb-[max(env(safe-area-inset-bottom),16px)] pt-12 backdrop-blur-sm sm:items-center sm:pt-0"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`dlg-${request.id}-title`}
        data-modal="sheet"
        data-state={closing ? "closing" : "open"}
        className="relative w-full max-w-md overflow-hidden rounded-2xl border border-ink/10 bg-paper shadow-2xl shadow-ink/30"
      >
        <span className={`absolute inset-x-0 top-0 h-1 ${tone.bar}`} aria-hidden />
        <div className="flex items-start gap-3 p-5 pt-6">
          <span
            aria-hidden
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border ${tone.chip} text-base font-bold`}
          >
            {ICON[variant]}
          </span>
          <div className="min-w-0 flex-1">
            <h2
              id={`dlg-${request.id}-title`}
              className="serif text-lg font-semibold tracking-tight text-ink balanced"
            >
              {request.kind === "confirm" || request.kind === "prompt" || request.kind === "alert"
                ? request.options.title
                : ""}
            </h2>
            {("body" in request.options && request.options.body) ? (
              <p className="mt-2 text-sm text-ink/70 leading-relaxed pretty break-words [overflow-wrap:anywhere]">
                {request.options.body}
              </p>
            ) : null}
            {request.kind === "prompt" ? (
              <PromptBody
                request={request}
                tone={tone}
                onCancel={cancel}
                onAnimatedDismiss={animatedDismiss}
                inputRef={firstFocusableRef as React.RefObject<HTMLInputElement>}
              />
            ) : null}
            {request.kind === "confirm" ? (
              <ConfirmBody
                request={request}
                tone={tone}
                onCancel={cancel}
                onAnimatedDismiss={animatedDismiss}
                buttonRef={firstFocusableRef as React.RefObject<HTMLButtonElement>}
              />
            ) : null}
            {request.kind === "alert" ? (
              <AlertBody
                request={request}
                tone={tone}
                onClose={cancel}
                buttonRef={firstFocusableRef as React.RefObject<HTMLButtonElement>}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function ConfirmBody({
  request,
  tone,
  onCancel,
  onAnimatedDismiss,
  buttonRef,
}: {
  request: Extract<DialogRequest, { kind: "confirm" }>;
  tone: { cta: string };
  onCancel: () => void;
  onAnimatedDismiss: () => void;
  buttonRef: React.RefObject<HTMLButtonElement>;
}) {
  const [typed, setTyped] = useState("");
  const expected = request.options.requireType?.trim();
  const matches = !expected || typed.trim() === expected;
  return (
    <>
      {expected ? (
        <label className="mt-3 grid gap-1 text-xs text-ink/60">
          <span>
            Type <code className="mono text-ink">{expected}</code> to confirm.
          </span>
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm focus-ring focus:border-gold focus:outline-none"
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
          />
        </label>
      ) : null}
      <div className="mt-4 flex flex-row flex-nowrap items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="min-h-[40px] inline-flex items-center justify-center rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-medium text-ink/75 hover:bg-ink/5 focus-ring"
        >
          {request.options.cancelLabel ?? "Cancel"}
        </button>
        <button
          ref={buttonRef}
          disabled={!matches}
          onClick={() => {
            request.resolve(true);
            onAnimatedDismiss();
          }}
          className={
            "min-h-[40px] inline-flex items-center justify-center whitespace-nowrap rounded-lg border px-4 py-2 text-sm font-semibold focus-ring disabled:cursor-not-allowed disabled:opacity-60 " +
            tone.cta
          }
        >
          {request.options.confirmLabel ?? "Confirm"}
        </button>
      </div>
    </>
  );
}

function PromptBody({
  request,
  tone,
  onCancel,
  onAnimatedDismiss,
  inputRef,
}: {
  request: Extract<DialogRequest, { kind: "prompt" }>;
  tone: { cta: string };
  onCancel: () => void;
  onAnimatedDismiss: () => void;
  inputRef: React.RefObject<HTMLInputElement>;
}) {
  const [value, setValue] = useState(request.options.defaultValue ?? "");
  const [touched, setTouched] = useState(false);

  const validation = useMemo(() => {
    if (!request.options.validate) return null;
    return request.options.validate(value) ?? null;
  }, [value, request.options]);

  const strength = useMemo(() => strengthOf(value), [value]);

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    setTouched(true);
    if (validation) return;
    request.resolve(value);
    onAnimatedDismiss();
  }

  return (
    <form className="mt-3 grid gap-2" onSubmit={submit}>
      <label className="grid gap-1 text-xs text-ink/65">
        {request.options.label ? <span>{request.options.label}</span> : null}
        <input
          ref={inputRef}
          type={request.options.inputType ?? "text"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => setTouched(true)}
          placeholder={request.options.placeholder}
          autoComplete={request.options.inputType === "password" ? "new-password" : "off"}
          autoCapitalize="off"
          spellCheck={false}
          className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm focus-ring focus:border-gold focus:outline-none"
        />
      </label>
      {request.options.strengthMeter ? <StrengthBar score={strength.score} label={strength.label} /> : null}
      {touched && validation ? (
        <p className="text-[11px] text-rust">{validation}</p>
      ) : null}
      <div className="mt-2 flex flex-row flex-nowrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="min-h-[40px] inline-flex items-center justify-center rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-medium text-ink/75 hover:bg-ink/5 focus-ring"
        >
          {request.options.cancelLabel ?? "Cancel"}
        </button>
        <button
          type="submit"
          disabled={!!validation}
          className={
            "min-h-[40px] inline-flex items-center justify-center whitespace-nowrap rounded-lg border px-4 py-2 text-sm font-semibold focus-ring disabled:cursor-not-allowed disabled:opacity-60 " +
            tone.cta
          }
        >
          {request.options.confirmLabel ?? "Continue"}
        </button>
      </div>
    </form>
  );
}

function AlertBody({
  request,
  tone,
  onClose,
  buttonRef,
}: {
  request: Extract<DialogRequest, { kind: "alert" }>;
  tone: { cta: string };
  onClose: () => void;
  buttonRef: React.RefObject<HTMLButtonElement>;
}) {
  return (
    <div className="mt-4 flex justify-end">
      <button
        ref={buttonRef}
        onClick={onClose}
        className={
          "min-h-[40px] inline-flex items-center justify-center whitespace-nowrap rounded-lg border px-4 py-2 text-sm font-semibold focus-ring " +
          tone.cta
        }
      >
        {request.options.confirmLabel ?? "OK"}
      </button>
    </div>
  );
}

function strengthOf(s: string): { score: number; label: string } {
  let score = 0;
  if (s.length >= 8) score++;
  if (s.length >= 14) score++;
  if (/[a-z]/.test(s) && /[A-Z]/.test(s)) score++;
  if (/[0-9]/.test(s)) score++;
  if (/[^A-Za-z0-9]/.test(s)) score++;
  const labels = ["empty", "weak", "okay", "good", "strong", "excellent"];
  return { score, label: labels[Math.min(score, 5)] };
}

function StrengthBar({ score, label }: { score: number; label: string }) {
  const TONE = ["bg-ink/15", "bg-rust", "bg-rust", "bg-gold", "bg-fern", "bg-fern"];
  return (
    <div className="grid gap-1">
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={"h-1 flex-1 rounded-full " + (i < score ? TONE[score] : "bg-ink/8")}
          />
        ))}
      </div>
      <span className="text-[10px] text-ink/50 mono">{label}</span>
    </div>
  );
}
