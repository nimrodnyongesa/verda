import { ReactNode } from "react";

export function Card({
  children,
  className = "",
  tone = "paper",
}: {
  children: ReactNode;
  className?: string;
  tone?: "paper" | "deep" | "ink";
}) {
  const tones = {
    paper: "surface",
    deep: "surface-deep",
    ink: "surface-ink",
  } as const;
  return <section className={tones[tone] + " " + className}>{children}</section>;
}

export function CardHeader({
  title,
  subtitle,
  right,
  className = "",
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={"flex items-start justify-between gap-4 border-b border-ink/8 px-5 py-4 " + className}>
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-xs text-ink/55">{subtitle}</p> : null}
      </div>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={"p-5 " + className}>{children}</div>;
}
