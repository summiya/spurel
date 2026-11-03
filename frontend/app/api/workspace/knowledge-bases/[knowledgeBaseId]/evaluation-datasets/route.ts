import { type NextRequest, NextResponse } from "next/server";
import { parseEvaluationPayload } from "@/lib/evaluation-types";
import { backendRequest, pageOffset, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string }> };
const MAX_BODY_BYTES = 32_768;

export async function GET(request: NextRequest, context: Context) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);
  const { knowledgeBaseId } = await context.params;
  const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
  if (!validUUID(knowledgeBaseId) || offset === null)
    return noStore(NextResponse.json({ error: "Invalid dataset listing." }, { status: 400 }));
  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/evaluation-datasets?limit=50&offset=${offset}`,
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}

export async function POST(request: NextRequest, context: Context) {
  const denied = authFailure(request, true);
  if (denied) return noStore(denied);
  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId))
    return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));
  if (Number(request.headers.get("content-length") ?? 0) > MAX_BODY_BYTES)
    return noStore(NextResponse.json({ error: "Request is too large." }, { status: 413 }));
  let input: unknown;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES)
      return noStore(NextResponse.json({ error: "Request is too large." }, { status: 413 }));
    input = JSON.parse(raw);
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON." }, { status: 400 }));
  }
  const payload = parseEvaluationPayload("dataset", input);
  if (!payload)
    return noStore(NextResponse.json({ error: "Invalid dataset name." }, { status: 422 }));
  try {
    const result = await backendRequest(`/knowledge-bases/${knowledgeBaseId}/evaluation-datasets`, {
      method: "POST", body: JSON.stringify(payload),
    });
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
