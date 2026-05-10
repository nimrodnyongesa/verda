import Link from "next/link";
import Image from "next/image";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export default async function NotFound() {
  const { messages, fallback } = await getMessages();
  const t = (key: string) => format(messages, fallback, key);
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
          <p className="mono text-[11px] uppercase tracking-[0.18em] text-ink/45">
            {t("notFound.kicker")}
          </p>
          <h1 className="serif mt-2 text-3xl font-bold tracking-tight balanced sm:text-4xl">
            {t("notFound.title")}
          </h1>
          <p className="mt-3 max-w-prose text-sm text-ink/65 leading-relaxed pretty">
            {t("notFound.body")}
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              href="/"
              className="inline-flex min-h-[40px] items-center rounded-lg bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-soft focus-ring"
            >
              {t("notFound.backHome")}
            </Link>
            <Link
              href="/cases"
              className="inline-flex min-h-[40px] items-center rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm text-ink/75 hover:border-ink/30 hover:text-ink focus-ring"
            >
              {t("notFound.allCases")}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
