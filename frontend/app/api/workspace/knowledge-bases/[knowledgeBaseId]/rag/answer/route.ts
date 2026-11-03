import { type NextRequest, NextResponse } from "next/server";

import { parseRagAnswerRequest } from "@/lib/rag-types";
import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string }> };
const MAX_REQUEST_BYTES = 40_960;

/** An exact, operator-authenticated RAG endpoint; never a generic browser proxy. */
export async function POST(request: NextRequest, context: Context) {
  const denied = authFailure(request, true);
  if (denied) return noStore(denied);

  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId)) {
    return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));
  }
  if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
    return noStore(NextResponse.json({ error: "RAG request is too large." }, { status: 413 }));
  }

  let body: unknown;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) {
      return noStore(NextResponse.json({ error: "RAG request is too large." }, { status: 413 }));
    }
    body = JSON.parse(raw);
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON request." }, { status: 400 }));
  }

  const payload = parseRagAnswerRequest(body);
  if (!payload) {
    return noStore(
      NextResponse.json(
        {
          error:
            "Question must be 1–8,000 characters; Top K 1–20, Candidate K from Top K to 100, and RRF K 1–1,000.",
        },
        { status: 422 },
      ),
    );
  }

  try {
    const result = await backendRequest(`/knowledge-bases/${knowledgeBaseId}/rag/answer`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 180_000,
    });
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
