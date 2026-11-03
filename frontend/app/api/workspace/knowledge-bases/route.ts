import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, pageOffset, safeBackendError } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

export async function GET(request: NextRequest) {
  const failure = authFailure(request);
  if (failure) return noStore(failure);
  const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
  if (offset === null) return noStore(NextResponse.json({ error: "Invalid page offset." }, { status: 400 }));
  try {
    const result = await backendRequest(`/knowledge-bases?limit=50&offset=${offset}`);
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}

export async function POST(request: NextRequest) {
  const failure = authFailure(request, true);
  if (failure) return noStore(failure);
  if (Number(request.headers.get("content-length") ?? 0) > 2048) {
    return noStore(NextResponse.json({ error: "Request is too large." }, { status: 413 }));
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON." }, { status: 400 }));
  }
  const name =
    body && typeof body === "object" && "name" in body && typeof body.name === "string"
      ? body.name.trim()
      : "";
  if (!name || name.length > 120) {
    return noStore(
      NextResponse.json({ error: "Knowledge base name must be 1–120 characters." }, { status: 422 }),
    );
  }
  try {
    const result = await backendRequest("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
