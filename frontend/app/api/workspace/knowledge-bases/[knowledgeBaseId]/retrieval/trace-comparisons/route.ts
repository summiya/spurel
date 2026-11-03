import { type NextRequest, NextResponse } from "next/server";

import { parseTraceComparisonRequest } from "@/lib/trace-history-types";
import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string }> };
const MAX_REQUEST_BYTES = 2048;

export async function POST(request: NextRequest, context: Context) {
  const denied = authFailure(request, true);
  if (denied) return noStore(denied);
  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId)) {
    return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));
  }
  if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
    return noStore(NextResponse.json({ error: "Comparison request is too large." }, { status: 413 }));
  }

  let raw: unknown;
  try {
    const text = await request.text();
    if (text.length > MAX_REQUEST_BYTES) {
      return noStore(NextResponse.json({ error: "Comparison request is too large." }, { status: 413 }));
    }
    raw = JSON.parse(text);
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON request." }, { status: 400 }));
  }
  const payload = parseTraceComparisonRequest(raw);
  if (!payload) {
    return noStore(NextResponse.json({
      error: "Choose two distinct saved retrieval trace IDs from the same knowledge base.",
    }, { status: 422 }));
  }

  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/retrieval/trace-comparisons`,
      { method: "POST", body: JSON.stringify(payload), timeoutMs: 30_000 },
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
