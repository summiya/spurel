import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { exportDownloadResponse, parseExportFormat } from "@/lib/server/export-download";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; traceId: string }> };

/** Scoped saved-trace export; no provider calls or browser-controlled upstream URLs. */
export async function GET(request: NextRequest, context: Context) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);

  const { knowledgeBaseId, traceId } = await context.params;
  if (!validUUID(knowledgeBaseId) || !validUUID(traceId)) {
    return noStore(NextResponse.json({ error: "Invalid retrieval trace reference." }, { status: 400 }));
  }
  const format = parseExportFormat(request.nextUrl.searchParams);
  if (!format) {
    return noStore(NextResponse.json({ error: "Choose JSON or CSV format." }, { status: 422 }));
  }

  try {
    const response = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/retrieval/traces/${traceId}/export?format=${format}`,
    );
    const download = exportDownloadResponse(
      response.payload, "retrieval_trace", traceId, format, knowledgeBaseId,
    );
    return download ?? noStore(NextResponse.json({ error: "Invalid export response." }, { status: 502 }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
