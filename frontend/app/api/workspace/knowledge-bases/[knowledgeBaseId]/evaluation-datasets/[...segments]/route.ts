import { type NextRequest, NextResponse } from "next/server";

import { parseEvaluationPayload } from "@/lib/evaluation-types";
import { evaluationOperation } from "@/lib/evaluation-route-contract";
import {
  backendRequest,
  pageOffset,
  safeBackendError,
  validUUID,
} from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

type Context = { params: Promise<{ knowledgeBaseId: string; segments: string[] }> };
const MAX_BODY_BYTES = 32_768;

async function handler(request: NextRequest, context: Context) {
  const mutation = request.method !== "GET";
  const denied = authFailure(request, mutation);
  if (denied) return noStore(denied);

  const { knowledgeBaseId, segments } = await context.params;
  if (
    !validUUID(knowledgeBaseId) ||
    !Array.isArray(segments) ||
    segments.length < 2 ||
    !validUUID(segments[0])
  ) {
    return noStore(NextResponse.json({ error: "Invalid evaluation reference." }, { status: 400 }));
  }

  const operation = evaluationOperation(segments.slice(1), validUUID, request.method);
  if (!operation)
    return noStore(NextResponse.json({ error: "Unknown evaluation operation." }, { status: 404 }));

  let path = `/knowledge-bases/${knowledgeBaseId}/evaluation-datasets/${segments.join("/")}`;
  if (operation.mode === "read" && operation.paginated) {
    const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
    if (offset === null)
      return noStore(NextResponse.json({ error: "Invalid page offset." }, { status: 400 }));
    path += `?limit=50&offset=${offset}`;
  }

  let body: string | undefined;
  if (operation.mode === "write") {
    if (Number(request.headers.get("content-length") ?? 0) > MAX_BODY_BYTES)
      return noStore(NextResponse.json({ error: "Request is too large." }, { status: 413 }));
    let raw: unknown;
    try {
      const text = await request.text();
      if (new TextEncoder().encode(text).byteLength > MAX_BODY_BYTES)
        return noStore(NextResponse.json({ error: "Request is too large." }, { status: 413 }));
      raw = JSON.parse(text);
    } catch {
      return noStore(NextResponse.json({ error: "Invalid JSON." }, { status: 400 }));
    }
    const payload = parseEvaluationPayload(operation.kind, raw);
    if (!payload)
      return noStore(NextResponse.json({ error: "Invalid evaluation request." }, { status: 422 }));
    body = JSON.stringify(payload);
  }

  try {
    const result = await backendRequest(path, {
      method: operation.mode === "write" ? operation.method : "GET",
      body,
      timeoutMs:
        operation.mode === "write" && ["keyword", "vector", "hybrid"].includes(operation.kind)
          ? 180_000
          : 30_000,
    });
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (cause) {
    const safe = safeBackendError(cause);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}

export async function GET(request: NextRequest, context: Context) {
  return handler(request, context);
}
export async function POST(request: NextRequest, context: Context) {
  return handler(request, context);
}
export async function PUT(request: NextRequest, context: Context) {
  return handler(request, context);
}
