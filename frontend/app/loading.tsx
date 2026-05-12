import Image from "next/image";
import { getMessages } from "@/lib/i18n/server";
import { format } from "@/lib/i18n/format";

export default async function Loading() {
  const { messages, fallback } = await getMessages();
  return (
    <div className="mx-auto flex min-h-[calc(100dvh-220px)] max-w-3xl items-center justify-center px-6 py-16">
      <div className="flex flex-col items-center gap-4 text-center">
        <Image
          src="/verda-mark.svg"
          alt=""
          width={64}
          height={64}
          aria-hidden="true"
          className="h-16 w-16 animate-pulse"
        />
        <p className="mono text-[11px] uppercase tracking-[0.18em] text-ink/45">
          {format(messages, fallback, "loading")}
        </p>
      </div>
    </div>
  );
}
