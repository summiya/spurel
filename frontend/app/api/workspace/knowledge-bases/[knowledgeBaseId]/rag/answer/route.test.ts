import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const mocks = vi.hoisted(() => ({
  authFailure: vi.fn(),
  backendRequest: vi.fn(),
}));

vi.mock("@/lib/server/backend-client", () => ({
  validUUID: (value: string) =>
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value),
  backendRequest: mocks.backendRequest,
  safeBackendError: () => ({ status: 503, error: "Backend temporarily unavailable." }),
}));

vi.mock("@/lib/server/operator-session", () => ({
  authFailure: mocks.authFailure,
  noStore: (response: NextResponse) => {
    response.headers.set("Cache-Control", "no-store");
    return response;
  },
}));

const kb = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const payload = {
  query: "Policy question",
  top_k: 8,
  candidate_k: 50,
  rrf_k: 60,
};

function request(body: string, headers: Record<string, string> = {}): NextRequest {
  return new NextRequest(`http://localhost:3000/api/workspace/knowledge-bases/${kb}/rag/answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: "http://localhost:3000",
      ...headers,
    },
    body,
  });
}

function context(knowledgeBaseId = kb) {
  return { params: Promise.resolve({ knowledgeBaseId }) };
}

describe("SP-15 exact RAG frontend API route", () => {
  beforeEach(() => {
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockReset();
    mocks.backendRequest.mockResolvedValue({ status: 200, payload: { trace_id: kb } });
  });

  it("forwards only a validated explicit request to the fixed RAG endpoint", async () => {
    const response = await POST(request(JSON.stringify(payload)), context());
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(mocks.authFailure).toHaveBeenCalledWith(expect.any(NextRequest), true);
    expect(mocks.backendRequest).toHaveBeenCalledWith(`/knowledge-bases/${kb}/rag/answer`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 180_000,
    });
  });

  it("rejects unauthenticated and cross-origin sessions before making any upstream call", async () => {
    mocks.authFailure.mockReturnValueOnce(
      NextResponse.json({ error: "Operator sign-in required." }, { status: 401 }),
    );
    const denied = await POST(request(JSON.stringify(payload)), context());
    expect(denied.status).toBe(401);
    expect(mocks.backendRequest).not.toHaveBeenCalled();

    mocks.authFailure.mockReturnValueOnce(
      NextResponse.json({ error: "Cross-origin modification rejected." }, { status: 403 }),
    );
    const rejected = await POST(
      request(JSON.stringify(payload), {
        Origin: "http://untrusted.example",
      }),
      context(),
    );
    expect(rejected.status).toBe(403);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("rejects invalid KB UUIDs, unsupported settings, invalid JSON and oversized requests", async () => {
    const invalidId = await POST(request(JSON.stringify(payload)), context("invalid-id"));
    expect(invalidId.status).toBe(400);

    const invalidSettings = await POST(
      request(JSON.stringify({ ...payload, top_k: 50 })),
      context(),
    );
    expect(invalidSettings.status).toBe(422);

    const invalidJson = await POST(request("{not-json"), context());
    expect(invalidJson.status).toBe(400);

    const huge = await POST(
      request(JSON.stringify(payload), { "Content-Length": "50000" }),
      context(),
    );
    expect(huge.status).toBe(413);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("returns sanitized upstream errors without exposing secrets", async () => {
    mocks.backendRequest.mockRejectedValueOnce(new Error("secret provider key"));
    const response = await POST(request(JSON.stringify(payload)), context());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "Backend temporarily unavailable." });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });
});
