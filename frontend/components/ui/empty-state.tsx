import { ReactNode } from "react";

export function EmptyState({
  title,
  body,
  action,
  icon = "✦",
  className = "",
}: {
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={"flex flex-col items-center justify-center rounded-xl border border-dashed border-ink/15 bg-paper-deep/30 px-8 py-12 text-center " + className}>
      <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-gold-soft/70 text-ink">
        <span className="text-base">{icon}</span>
      </div>
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {body ? <p className="mt-1.5 max-w-sm text-sm text-ink/60">{body}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
