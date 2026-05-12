import { NextResponse } from "next/server";
import { AUTH_ENABLED } from "@/lib/auth/config";
import { getSession } from "@/lib/auth/session";

export async function GET() {
  if (!AUTH_ENABLED) {
    return NextResponse.json({ enabled: false, user: null });
  }
  const session = await getSession();
  return NextResponse.json({
    enabled: true,
    user: session
      ? {
          sub: session.user.sub,
          email: session.user.email,
          name: session.user.name,
          providerId: session.providerId,
        }
      : null,
  });
}
