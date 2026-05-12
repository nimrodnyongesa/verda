"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect } from "react";
import { useT } from "@/lib/i18n/provider";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  useEffect(() => {
    console.error("[Verda] page error", error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-220px)] max-w-3xl items-center px-6 py-16">
      <div className="grid w-full gap-6 sm:grid-cols-[auto_1fr] sm:items-center sm:gap-8">
        <Image
          src="/verda-mark.svg"
          alt=""
          width={96}
          height={96}
          aria-hidden="true"
          className="h-20 w-20 sm:h-24 sm:w-24"
        />
        <div>
          <p className="mono text-[11px] uppercase tracking-[0.18em] text-rust">
            {t("error.kicker")}
          </p>
          <h1 className="serif mt-2 text-3xl font-bold tracking-tight balanced sm:text-4xl">
            {t("error.title")}
          </h1>
          <p className="mt-3 max-w-prose text-sm text-ink/65 leading-relaxed pretty">
            {t("error.body")}
          </p>
          {error.message ? (
            <pre className="mt-4 max-h-40 overflow-auto rounded-lg border border-rust/30 bg-rust/5 px-3 py-2 text-[11px] text-rust whitespace-pre-wrap break-all">
              {error.message}
              {error.digest ? `\n\ndigest: ${error.digest}` : ""}
            </pre>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-2">
            <button
              onClick={() => reset()}
              className="inline-flex min-h-[40px] items-center rounded-lg bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft focus-ring"
            >
              {t("error.tryAgain")}
            </button>
            <Link
              href="/"
              className="inline-flex min-h-[40px] items-center rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm text-ink/75 hover:border-ink/30 hover:text-ink focus-ring"
            >
              {t("error.backHome")}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
