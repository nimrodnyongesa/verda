"use client";

export type ToastVariant = "info" | "success" | "error";

export type Toast = {
  id: string;
  title: string;
  body?: string;
  variant: ToastVariant;
  durationMs: number;
  createdAt: number;
};

type Listener = (toasts: Toast[]) => void;

const listeners = new Set<Listener>();
let queue: Toast[] = [];

function notify() {
  for (const fn of listeners) fn(queue.slice());
}

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  fn(queue.slice());
  return () => {
    listeners.delete(fn);
  };
}

export function pushToast(input: { title: string; body?: string; variant?: ToastVariant; durationMs?: number }) {
  const id = Math.random().toString(36).slice(2, 10);
  const toast: Toast = {
    id,
    title: input.title,
    body: input.body,
    variant: input.variant ?? "info",
    durationMs: input.durationMs ?? 4500,
    createdAt: Date.now(),
  };
  queue = [...queue, toast];
  notify();
  if (toast.durationMs > 0) {
    setTimeout(() => dismissToast(id), toast.durationMs);
  }
  return id;
}

export function dismissToast(id: string) {
  queue = queue.filter((t) => t.id !== id);
  notify();
}

export const toast = {
  info: (title: string, body?: string) => pushToast({ title, body, variant: "info" }),
  success: (title: string, body?: string) => pushToast({ title, body, variant: "success" }),
  error: (title: string, body?: string) => pushToast({ title, body, variant: "error", durationMs: 6500 }),
};
