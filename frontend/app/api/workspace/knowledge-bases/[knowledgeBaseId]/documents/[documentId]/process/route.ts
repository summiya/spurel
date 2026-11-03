import { type NextRequest, NextResponse } from "next/server";

import { parseChunkingOptions } from "@/lib/chunking-options";
import { backendRequest, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; documentId: string }> };
const MAX_REQUEST_BYTES = 2048;

export async function POST(request: NextRequest, context: Context) {
  const failure = authFailure(request, true);
  if (failure) return noStore(failure);

  const { knowledgeBaseId, documentId } = await context.params;
  if (!validUUID(knowledgeBaseId) || !validUUID(documentId)) {
    return noStore(NextResponse.json({ error: "Invalid document reference." }, { status: 400 }));
  }

  // Old callers send no body and retain the exact character chunker defaults.
  if (Number(request.headers.get("content-length") ?? 0) > MAX_REQUEST_BYTES) {
    return noStore(NextResponse.json({ error: "Chunking options are too large." }, { status: 413 }));
  }

  let body: string | undefined;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_REQUEST_BYTES) {
      return noStore(NextResponse.json({ error: "Chunking options are too large." }, { status: 413 }));
    }
    if (raw.trim()) {
      const options = parseChunkingOptions(JSON.parse(raw));
      if (!options) {
        return noStore(
          NextResponse.json({ error: "Invalid chunking mode, chunk size or overlap." }, { status: 422 }),
        );
      }
      body = JSON.stringify(options);
    }
  } catch {
    return noStore(NextResponse.json({ error: "Invalid JSON request." }, { status: 400 }));
  }

  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/process`,
      { method: "POST", body, timeoutMs: 180_000 },
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
