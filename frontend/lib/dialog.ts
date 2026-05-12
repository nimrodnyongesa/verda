"use client";

// Promise-based custom dialog system.
//
//   await confirm({ title: "Sign out?", body: "..." })          // boolean
//   await prompt({ title: "Passphrase", placeholder: "…" })     // string | null
//   await alert({ title: "Done", body: "..." })                 // void
//
// One <DialogHost /> mounts in the root layout. This module exposes the
// imperative API client components import. No external dep.

export type DialogVariant = "info" | "warning" | "danger" | "success";

export type ConfirmOptions = {
  title: string;
  body?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: DialogVariant;
  /** Require the user to type a phrase (e.g. case name) to enable confirm. */
  requireType?: string;
};

export type PromptOptions = {
  title: string;
  body?: string;
  label?: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  inputType?: "text" | "password" | "email" | "url";
  variant?: DialogVariant;
  /** Optional client-side validator. Return null/empty for OK, or an error string. */
  validate?: (value: string) => string | null | undefined;
  /** Render a passphrase strength meter under the input. */
  strengthMeter?: boolean;
};

export type AlertOptions = {
  title: string;
  body?: string;
  confirmLabel?: string;
  variant?: DialogVariant;
};

type ConfirmRequest = {
  kind: "confirm";
  id: string;
  options: ConfirmOptions;
  resolve: (ok: boolean) => void;
};
type PromptRequest = {
  kind: "prompt";
  id: string;
  options: PromptOptions;
  resolve: (value: string | null) => void;
};
type AlertRequest = {
  kind: "alert";
  id: string;
  options: AlertOptions;
  resolve: () => void;
};
export type DialogRequest = ConfirmRequest | PromptRequest | AlertRequest;

type Listener = (queue: DialogRequest[]) => void;

const listeners = new Set<Listener>();
let queue: DialogRequest[] = [];

function notify() {
  const snapshot = queue.slice();
  for (const fn of listeners) fn(snapshot);
}

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  fn(queue.slice());
  return () => {
    listeners.delete(fn);
  };
}

export function close(id: string) {
  queue = queue.filter((q) => q.id !== id);
  notify();
}

function id(): string {
  return Math.random().toString(36).slice(2, 10);
}

function isClient(): boolean {
  return typeof window !== "undefined";
}

export function confirm(options: ConfirmOptions): Promise<boolean> {
  if (!isClient()) return Promise.resolve(false);
  return new Promise<boolean>((resolve) => {
    queue = [
      ...queue,
      {
        kind: "confirm",
        id: id(),
        options,
        resolve,
      },
    ];
    notify();
  });
}

export function prompt(options: PromptOptions): Promise<string | null> {
  if (!isClient()) return Promise.resolve(null);
  return new Promise<string | null>((resolve) => {
    queue = [
      ...queue,
      {
        kind: "prompt",
        id: id(),
        options,
        resolve,
      },
    ];
    notify();
  });
}

export function alert(options: AlertOptions): Promise<void> {
  if (!isClient()) return Promise.resolve();
  return new Promise<void>((resolve) => {
    queue = [
      ...queue,
      {
        kind: "alert",
        id: id(),
        options,
        resolve,
      },
    ];
    notify();
  });
}

// Convenience wrapper for "danger" destructive flows.
export function confirmDanger(input: Omit<ConfirmOptions, "variant">) {
  return confirm({ variant: "danger", ...input });
}

// Default export — when client code wants to alias for `window.confirm`-shape code.
export const dialog = { confirm, prompt, alert, confirmDanger };
