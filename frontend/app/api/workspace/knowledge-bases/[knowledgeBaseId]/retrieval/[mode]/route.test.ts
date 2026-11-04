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
const doc = "d73b06d7-a20e-4ddf-9859-242d69d4372f";

function request(mode: string, body: string, headers: Record<string, string> = {}) {
  return new NextRequest(
    `http://localhost:3000/api/workspace/knowledge-bases/${kb}/retrieval/${mode}`,
    {
      method: "POST",
      body,
      headers: {
        Origin: "http://localhost:3000",
        "Content-Type": "application/json",
        ...headers,
      },
    },
  );
}

function context(knowledgeBaseId = kb, mode = "keyword") {
  return { params: Promise.resolve({ knowledgeBaseId, mode }) };
}

describe("SP-19 retrieval metadata API proxy", () => {
  beforeEach(() => {
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockReset();
    mocks.backendRequest.mockResolvedValue({
      status: 200,
      payload: { mode: "keyword", matches: [] },
    });
  });

  it("retains legacy unfiltered requests and does not add filter keys", async () => {
    const body = { query: "policy", top_k: 5 };
    const response = await POST(request("keyword", JSON.stringify(body)), context());
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(mocks.backendRequest).toHaveBeenCalledWith(`/knowledge-bases/${kb}/retrieval/keyword`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 60000,
    });
  });

  it("forwards identical validated filters for keyword, vector and hybrid", async () => {
    const filters = {
      document_ids: [doc],
      media_types: ["application/pdf"],
      filename_contains: "policy",
    };
    for (const mode of ["keyword", "vector", "hybrid"]) {
      mocks.backendRequest.mockClear();
      const body = {
        query: "refund",
        top_k: 8,
        ...(mode === "hybrid" ? { candidate_k: 50, rrf_k: 60 } : {}),
        filters,
      };
      const response = await POST(request(mode, JSON.stringify(body)), context(kb, mode));
      expect(response.status).toBe(200);
      expect(mocks.backendRequest).toHaveBeenCalledWith(
        `/knowledge-bases/${kb}/retrieval/${mode}`,
        {
          method: "POST",
          body: JSON.stringify(body),
          timeoutMs: 60000,
        },
      );
    }
  });

  it("rejects unsupported criteria, invalid UUIDs, oversized or malformed payloads", async () => {
    const base = { query: "refund", top_k: 5 };
    const invalidFilters: unknown[] = [
      { unknown: "unsafe" },
      { document_ids: [doc, doc] },
      { filename_contains: " " },
      { media_types: ["text/html"] },
      { created_before: "2026-01-01T00:00:00Z", created_after: "2026-02-01T00:00:00Z" },
    ];
    for (const filters of invalidFilters) {
      const denied = await POST(
        request("keyword", JSON.stringify({ ...base, filters })),
        context(),
      );
      expect(denied.status).toBe(422);
    }
    expect((await POST(request("keyword", "{not-json"), context())).status).toBe(400);
    expect((await POST(request("keyword", JSON.stringify(base)), context("fake-id"))).status).toBe(
      400,
    );
    expect(
      (await POST(request("../../../rag", JSON.stringify(base)), context(kb, "../rag"))).status,
    ).toBe(400);
    const huge = await POST(
      request("keyword", JSON.stringify(base), { "Content-Length": "25000" }),
      context(),
    );
    expect(huge.status).toBe(413);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("authenticates and checks origin before contacting the backend", async () => {
    mocks.authFailure.mockReturnValueOnce(
      NextResponse.json({ error: "Operator sign-in required." }, { status: 401 }),
    );
    expect(
      (await POST(request("keyword", '{"query":"policy","top_k":10}'), context())).status,
    ).toBe(401);
    mocks.authFailure.mockReturnValueOnce(
      NextResponse.json({ error: "Cross-origin request rejected." }, { status: 403 }),
    );
    expect(
      (
        await POST(
          request("keyword", '{"query":"policy","top_k":10}', {
            Origin: "http://untrusted.example",
          }),
          context(),
        )
      ).status,
    ).toBe(403);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });
});
