import { type NextRequest, NextResponse } from "next/server";

import {
  backendRequest,
  pageOffset,
  safeBackendError,
  validUUID,
} from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; documentId: string }> };

export async function GET(request: NextRequest, context: Context) {
  const failure = authFailure(request);
  if (failure) return noStore(failure);

  const { knowledgeBaseId, documentId } = await context.params;
  if (!validUUID(knowledgeBaseId) || !validUUID(documentId)) {
    return noStore(NextResponse.json({ error: "Invalid document reference." }, { status: 400 }));
  }

  const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
  if (offset === null) {
    return noStore(NextResponse.json({ error: "Invalid page offset." }, { status: 400 }));
  }

  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/versions?limit=50&offset=${offset}`,
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const error = safeBackendError(cause);
    return noStore(NextResponse.json({ error: error.error }, { status: error.status }));
  }
}
