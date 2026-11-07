import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { exportDownloadResponse, parseExportFormat } from "@/lib/server/export-download";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = {
  params: Promise<{ knowledgeBaseId: string; datasetId: string; runId: string }>;
};

/** Read-only scoped benchmark download; never runs evaluations or generation. */
export async function GET(request: NextRequest, context: Context) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);

  const { knowledgeBaseId, datasetId, runId } = await context.params;
  if (![knowledgeBaseId, datasetId, runId].every(validUUID)) {
    return noStore(NextResponse.json({ error: "Invalid evaluation run reference." }, { status: 400 }));
  }
  const format = parseExportFormat(request.nextUrl.searchParams);
  if (!format) {
    return noStore(NextResponse.json({ error: "Choose JSON or CSV format." }, { status: 422 }));
  }

  try {
    const response = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/evaluation-datasets/${datasetId}/runs/${runId}/export?format=${format}`,
    );
    const download = exportDownloadResponse(
      response.payload, "evaluation_run", runId, format, knowledgeBaseId, datasetId,
    );
    return download ?? noStore(NextResponse.json({ error: "Invalid export response." }, { status: 502 }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
