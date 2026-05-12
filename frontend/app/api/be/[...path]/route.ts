// Authenticated proxy: forwards browser-originated requests to the FastAPI
// backend with the Bearer token from the session cookie. Use `/api/be/...`
// from any Client Component instead of calling FastAPI directly when auth
// is enabled.
import { NextRequest } from "next/server";
import { getAccessToken } from "@/lib/auth/session";

const BACKEND =
  process.env.WAKILI_INTERNAL_API_BASE ?? "http://127.0.0.1:8765";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

async function forward(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search ?? "";
  const target = `${BACKEND.replace(/\/$/, "")}/api/${path.map(encodeURIComponent).join("/")}${search}`;
  const headers = new Headers();
  for (const [key, value] of req.headers) {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  }
  const token = await getAccessToken().catch(() => null);
  if (token) headers.set("authorization", `Bearer ${token}`);
  // Keep Content-Type the browser set (FormData boundary, JSON, etc.).

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    // Required by undici when streaming a body without Content-Length.
    (init as RequestInit & { duplex?: "half" }).duplex = "half";
  }
  const res = await fetch(target, init);
  const out = new Headers();
  for (const [key, value] of res.headers) {
    if (!HOP_BY_HOP.has(key.toLowerCase())) out.set(key, value);
  }
  return new Response(res.body, { status: res.status, headers: out });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function PATCH(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
