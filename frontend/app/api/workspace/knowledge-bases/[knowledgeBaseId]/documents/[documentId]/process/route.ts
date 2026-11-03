import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; documentId: string }> };

export async function POST(request: NextRequest, context: Context) {
  const failure = authFailure(request, true);
  if (failure) return noStore(failure);
  const { knowledgeBaseId, documentId } = await context.params;
  if (!validUUID(knowledgeBaseId) || !validUUID(documentId)) {
    return noStore(NextResponse.json({ error: "Invalid document reference." }, { status: 400 }));
  }
  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/process`,
      { method: "POST", timeoutMs: 180_000 },
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
