import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const mocks = vi.hoisted(() => ({ authFailure: vi.fn(), backendRequest: vi.fn() }));
vi.mock("@/lib/server/backend-client", () => ({
  validUUID: (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value),
  backendRequest: mocks.backendRequest,
  safeBackendError: () => ({ status: 503, error: "Backend unavailable." }),
}));
vi.mock("@/lib/server/operator-session", () => ({
  authFailure: mocks.authFailure,
  noStore: (response: NextResponse) => {
    response.headers.set("Cache-Control", "no-store");
    return response;
  },
}));

const kb = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const doc = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const upstream = `/knowledge-bases/${kb}/documents/${doc}/process`;
const url = `http://localhost:3000/api/workspace/knowledge-bases/${kb}/documents/${doc}/process`;
function ctx(knowledgeBaseId = kb, documentId = doc) {
  return { params: Promise.resolve({ knowledgeBaseId, documentId }) };
}
function request(body?: string, headers?: Record<string, string>): NextRequest {
  return new NextRequest(url, {
    method: "POST",
    headers: { Origin: "http://localhost:3000", ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
    body,
  });
}

describe("SP-16 authenticated document processing proxy", () => {
  beforeEach(() => {
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockReset();
    mocks.backendRequest.mockResolvedValue({ status: 200, payload: { status: "processed" } });
  });

  it("retains original bodyless character-processing behavior", async () => {
    const response = await POST(request(), ctx());
    expect(response.status).toBe(200);
    expect(mocks.backendRequest).toHaveBeenCalledWith(upstream, {
      method: "POST", timeoutMs: 180000,
    });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });

  it("forwards only strictly validated explicit token-based settings", async () => {
    const body = { strategy: "tokens", chunk_size: 512, overlap: 64 };
    const response = await POST(request(JSON.stringify(body)), ctx());
    expect(response.status).toBe(200);
    expect(mocks.backendRequest).toHaveBeenCalledWith(upstream, {
      method: "POST", body: JSON.stringify(body), timeoutMs: 180000,
    });
    expect(mocks.authFailure).toHaveBeenCalledWith(expect.any(NextRequest), true);
  });

  it("rejects unknown or invalid options without upstream/provider calls", async () => {
    for (const body of [
      JSON.stringify({ strategy: "tokens", chunk_size: 2001, overlap: 200 }),
      JSON.stringify({ strategy: "tokens", chunk_size: 512, overlap: 512 }),
      JSON.stringify({ strategy: "other", chunk_size: 512, overlap: 20 }),
      JSON.stringify({ strategy: "tokens", chunk_size: 512, overlap: 20, unsafe: "yes" }),
    ]) {
      expect((await POST(request(body), ctx())).status).toBe(422);
    }
    expect((await POST(request("{invalid"), ctx())).status).toBe(400);
    expect((await POST(request(JSON.stringify({})), ctx("invalid-id"))).status).toBe(400);
    expect((await POST(request(" ".repeat(2500)), ctx())).status).toBe(413);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("protects operator sessions and cross-origin writes", async () => {
    mocks.authFailure.mockReturnValueOnce(NextResponse.json({ error: "Login required" }, { status: 401 }));
    expect((await POST(request(), ctx())).status).toBe(401);
    mocks.authFailure.mockReturnValueOnce(NextResponse.json({ error: "Cross origin" }, { status: 403 }));
    expect((await POST(request(JSON.stringify({ strategy: "tokens", chunk_size: 512, overlap: 64 }), { Origin: "http://evil.example" }), ctx())).status).toBe(403);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });
});
