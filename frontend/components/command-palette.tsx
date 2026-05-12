"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useSheetExit } from "@/lib/use-sheet-exit";
import { useT } from "@/lib/i18n/provider";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`/api/be${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

type Action = {
  id: string;
  label: string;
  hint?: string;
  group: string;
  run: () => void | Promise<void>;
};

function fuzzyScore(query: string, target: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t.includes(q)) return 1 + (10 - Math.min(10, t.indexOf(q)));
  let qi = 0;
  let score = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) {
      score += 1;
      qi++;
    }
  }
  return qi === q.length ? score / q.length : 0;
}

export function CommandPalette() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [recentCases, setRecentCases] = useState<{ id: number; title: string }[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const router = useRouter();
  const { closing, trigger: animatedClose } = useSheetExit(() => setOpen(false), 200);

  // Hotkey: ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) animatedClose();
        else setOpen(true);
      }
      if (e.key === "Escape" && open) {
        animatedClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, animatedClose]);

  useEffect(() => {
    if (open) {
      setActiveIdx(0);
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 10);
      // Fetch the first page of cases (server-side pagination kicks in for
      // > 25 — the palette shows the most recently-updated 8 to keep the
      // dropdown short; full search lives on the cases page).
      getJson<{ cases: { id: number; title: string }[] }>("/cases?per_page=8&page=1")
        .then((r) => setRecentCases(r.cases.slice(0, 8).map((c) => ({ id: c.id, title: c.title }))))
        .catch(() => setRecentCases([]));
    }
  }, [open]);

  const actions = useMemo<Action[]>(() => {
    const navigate = t("palette.groups.navigate");
    const actionsGroup = t("palette.groups.actions");
    const recent = t("palette.groups.recentCases");
    const base: Action[] = [
      {
        id: "go-home",
        label: t("palette.actions.home"),
        group: navigate,
        run: () => router.push("/"),
      },
      {
        id: "go-cases",
        label: t("palette.actions.allCases"),
        hint: "g c",
        group: navigate,
        run: () => router.push("/cases"),
      },
      {
        id: "go-audit",
        label: t("palette.actions.audit"),
        group: navigate,
        run: () => router.push("/audit"),
      },
      {
        id: "go-profile",
        label: t("palette.actions.profile"),
        group: navigate,
        run: () => router.push("/profile"),
      },
      {
        id: "new-case",
        label: t("palette.actions.newCase"),
        hint: t("palette.actions.newCaseHint"),
        group: actionsGroup,
        run: () => router.push("/"),
      },
    ];
    for (const c of recentCases) {
      base.push({
        id: `case-${c.id}`,
        label: c.title,
        hint: t("palette.actions.casePrefix", { id: c.id }),
        group: recent,
        run: () => router.push(`/cases/${c.id}`),
      });
    }
    return base;
  }, [recentCases, router, t]);

  const filtered = useMemo(() => {
    const scored = actions
      .map((a) => ({ a, s: fuzzyScore(query, a.label + " " + a.group + " " + (a.hint ?? "")) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s);
    return scored.map((x) => x.a);
  }, [actions, query]);

  if (!open) return null;

  // Group filtered results
  const groups = filtered.reduce<Record<string, Action[]>>((acc, a) => {
    (acc[a.group] = acc[a.group] || []).push(a);
    return acc;
  }, {});
  const flat = filtered;

  return (
    <div
      data-overlay
      data-state={closing ? "closing" : "open"}
      className="fixed inset-0 z-[200] flex items-start justify-center bg-ink/40 px-4 pt-24 backdrop-blur-sm"
      onClick={() => animatedClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        data-modal="sheet"
        data-state={closing ? "closing" : "open"}
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-ink/10 bg-paper shadow-2xl shadow-ink/30"
      >
        <div className="flex items-center gap-3 border-b border-ink/10 px-4 py-3">
          <span className="text-ink/40 text-sm">⌘K</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIdx(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIdx((i) => Math.min(flat.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIdx((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                const action = flat[activeIdx];
                if (action) {
                  animatedClose();
                  action.run();
                }
              }
            }}
            placeholder={t("palette.placeholder")}
            className="flex-1 bg-transparent text-base outline-none placeholder:text-ink/40"
          />
        </div>
        <div className="max-h-[60vh] overflow-y-auto py-2">
          {flat.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-ink/50">
              {t("palette.empty")}
            </div>
          ) : (
            Object.entries(groups).map(([group, items]) => (
              <div key={group} className="mb-2">
                <div className="px-4 pb-1 pt-2 text-[10px] uppercase tracking-[0.18em] text-ink/40">
                  {group}
                </div>
                <ul>
                  {items.map((a) => {
                    const idx = flat.indexOf(a);
                    const active = idx === activeIdx;
                    return (
                      <li key={a.id}>
                        <button
                          onMouseEnter={() => setActiveIdx(idx)}
                          onClick={() => {
                            animatedClose();
                            a.run();
                          }}
                          className={
                            "flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition " +
                            (active
                              ? "bg-ink text-paper"
                              : "hover:bg-ink/5 text-ink")
                          }
                        >
                          <span className="truncate">{a.label}</span>
                          {a.hint ? (
                            <span
                              className={
                                "shrink-0 mono text-[11px] " +
                                (active ? "text-paper/70" : "text-ink/40")
                              }
                            >
                              {a.hint}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
        </div>
        <div className="flex items-center justify-between border-t border-ink/10 px-4 py-2 text-[11px] text-ink/45">
          <span>{t("palette.footer")}</span>
          <span>v0.2 · localhost</span>
        </div>
      </div>
    </div>
  );
}
