import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; traceId: string }> };

export async function GET(request: NextRequest, context: Context) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);
  const { knowledgeBaseId, traceId } = await context.params;
  if (!validUUID(knowledgeBaseId) || !validUUID(traceId)) {
    return noStore(
      NextResponse.json({ error: "Invalid retrieval trace reference." }, { status: 400 }),
    );
  }
  try {
    const response = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/retrieval/traces/${traceId}`,
    );
    return noStore(NextResponse.json(response.payload, { status: response.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
