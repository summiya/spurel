import { type NextRequest, NextResponse } from "next/server";

import { isRetrievalMode, parseRetrievalRequest } from "@/lib/retrieval-types";
import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; mode: string }> };
const MAX_REQUEST_BYTES = 16_384;

export async function POST(request: NextRequest, context: Context) {
  const denied = authFailure(request, true);
  if (denied) return noStore(denied);
  const { knowledgeBaseId, mode } = await context.params;
  if (!validUUID(knowledgeBaseId) || !isRetrievalMode(mode)) {
    return noStore(
      NextResponse.json({ error: "Invalid retrieval target or mode." }, { status: 400 }),
    );
  }
  if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
    return noStore(
      NextResponse.json({ error: "Retrieval request is too large." }, { status: 413 }),
    );
  }

  let body: unknown;
  try {
    const raw = await request.text();
    if (raw.length > MAX_REQUEST_BYTES) {
      return noStore(
        NextResponse.json({ error: "Retrieval request is too large." }, { status: 413 }),
      );
    }
    body = JSON.parse(raw);
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON request." }, { status: 400 }));
  }
  const parsed = parseRetrievalRequest(mode, body);
  if (!parsed) {
    return noStore(
      NextResponse.json(
        {
          error:
            "Query must be 1–8,000 characters; Top K 1–100. For hybrid, Candidate K must be between Top K and 100, and RRF K between 1 and 1,000.",
        },
        { status: 422 },
      ),
    );
  }

  try {
    const response = await backendRequest(`/knowledge-bases/${knowledgeBaseId}/retrieval/${mode}`, {
      method: "POST",
      body: JSON.stringify(parsed),
      timeoutMs: 60_000,
    });
    return noStore(NextResponse.json(response.payload, { status: response.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
