import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, pageOffset, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string }> };

export async function GET(request: NextRequest, context: Context) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);

  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId)) {
    return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));
  }
  const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
  if (offset === null) {
    return noStore(NextResponse.json({ error: "Invalid page offset." }, { status: 400 }));
  }

  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/retrieval/traces?limit=50&offset=${offset}`,
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
