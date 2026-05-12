import { NextResponse } from "next/server";
import { AUTH_ENABLED, PROVIDERS } from "@/lib/auth/config";

export async function GET() {
  return NextResponse.json({
    enabled: AUTH_ENABLED,
    providers: PROVIDERS.map((p) => ({
      id: p.id,
      name: p.name,
      issuer: p.issuer,
      description: p.description,
    })),
  });
}
