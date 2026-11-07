import "server-only";

import { NextResponse } from "next/server";

export type ExportKind = "retrieval_trace" | "evaluation_run";
export type ExportFormat = "json" | "csv";

const MAX_EXPORT_BYTES = 5 * 1024 * 1024;

export function parseExportFormat(searchParams: URLSearchParams): ExportFormat | null {
  if (
    searchParams.size !== 1 ||
    searchParams.getAll("format").length !== 1
  ) return null;
  const value = searchParams.get("format");
  return value === "json" || value === "csv" ? value : null;
}

/**
 * Fail closed on a malformed backend download envelope and anchor the
 * attachment name/content type to the validated route, not upstream text.
 */
export function exportDownloadResponse(
  payload: unknown,
  kind: ExportKind,
  recordId: string,
  format: ExportFormat,
  knowledgeBaseId: string,
  datasetId?: string,
): NextResponse | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  const data = payload as Record<string, unknown>;
  const safeRecordId = recordId.toLowerCase();
  const expectedName =
    (kind === "retrieval_trace" ? "spurel-trace-" : "spurel-evaluation-run-") +
    safeRecordId +
    "." +
    format;
  const expectedMediaType = format === "json" ? "application/json" : "text/csv";
  if (
    data.filename !== expectedName ||
    data.media_type !== expectedMediaType ||
    typeof data.content !== "string" ||
    data.content.length < 1 ||
    new TextEncoder().encode(data.content).byteLength > MAX_EXPORT_BYTES
  ) return null;

  if (format === "json") {
    try {
      const parsed: unknown = JSON.parse(data.content);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
      const document = parsed as Record<string, unknown>;
      if (
        document.schema_version !== 1 ||
        document.artifact_type !== kind ||
        !document.source ||
        typeof document.source !== "object" ||
        Array.isArray(document.source)
      ) return null;
      const source = document.source as Record<string, unknown>;
      if (
        source.knowledge_base_id !== knowledgeBaseId.toLowerCase() ||
        source[kind === "retrieval_trace" ? "id" : "run_id"] !== safeRecordId ||
        (kind === "evaluation_run" && source.dataset_id !== datasetId?.toLowerCase())
      ) return null;
    } catch {
      return null;
    }
  } else {
    const header = data.content.split("\r\n", 1)[0];
    if (!header.startsWith("schema_version,artifact_type,") || !header.includes("record_count")) {
      return null;
    }
  }

  const response = new NextResponse(data.content, {
    status: 200,
    headers: {
      "Content-Type": expectedMediaType + "; charset=utf-8",
      "Content-Disposition": `attachment; filename="${expectedName}"`,
      "X-Content-Type-Options": "nosniff",
    },
  });
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}
