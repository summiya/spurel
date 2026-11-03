import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, pageOffset, safeBackendError, validUUID } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

const MAX_FILE_BYTES = 25 * 1024 * 1024;
const MEDIA_TYPES: Record<string, string> = {
  ".txt": "text/plain",
  ".md": "text/markdown",
  ".markdown": "text/markdown",
  ".pdf": "application/pdf",
};

type Context = { params: Promise<{ knowledgeBaseId: string }> };

function mediaType(filename: string): string | null {
  const ext = filename.toLowerCase().match(/\.[^.]+$/)?.[0] ?? "";
  return MEDIA_TYPES[ext] ?? null;
}

export async function GET(request: NextRequest, context: Context) {
  const failure = authFailure(request);
  if (failure) return noStore(failure);
  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId)) return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));
  const offset = pageOffset(request.nextUrl.searchParams.get("offset"));
  if (offset === null) return noStore(NextResponse.json({ error: "Invalid page offset." }, { status: 400 }));
  try {
    const result = await backendRequest(
      `/knowledge-bases/${knowledgeBaseId}/documents?limit=50&offset=${offset}`,
    );
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}

export async function POST(request: NextRequest, context: Context) {
  const failure = authFailure(request, true);
  if (failure) return noStore(failure);
  const { knowledgeBaseId } = await context.params;
  if (!validUUID(knowledgeBaseId)) return noStore(NextResponse.json({ error: "Invalid knowledge base." }, { status: 400 }));

  if (Number(request.headers.get("content-length") ?? 0) > MAX_FILE_BYTES + 1024 * 1024) {
    return noStore(NextResponse.json({ error: "Maximum upload size is 25 MB." }, { status: 413 }));
  }
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return noStore(NextResponse.json({ error: "Invalid file upload." }, { status: 400 }));
  }
  const value = form.get("file");
  if (!(value instanceof File) || value.size === 0 || value.size > MAX_FILE_BYTES) {
    return noStore(NextResponse.json({ error: "Select a nonempty file up to 25 MB." }, { status: 422 }));
  }
  if (!value.name || value.name.length > 255 || /[\\/\x00-\x1f\x7f]/.test(value.name)) {
    return noStore(NextResponse.json({ error: "Invalid document filename." }, { status: 422 }));
  }
  const type = mediaType(value.name);
  if (!type) {
    return noStore(NextResponse.json({ error: "Only PDF, Markdown, and text are supported." }, { status: 415 }));
  }
  const outgoing = new FormData();
  outgoing.set("file", new File([value], value.name, { type }));
  try {
    const result = await backendRequest(`/knowledge-bases/${knowledgeBaseId}/documents`, {
      method: "POST",
      body: outgoing,
      timeoutMs: 45_000,
    });
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
