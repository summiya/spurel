import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

const mocks = vi.hoisted(() => ({ authFailure: vi.fn(), backendRequest: vi.fn() }));

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
const trace = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const filename = `spurel-trace-${trace}`;

function request(query = "format=json") {
  return new NextRequest(`http://localhost:3000/api/workspace/knowledge-bases/${kb}/retrieval/traces/${trace}/export?${query}`);
}
function context(knowledgeBaseId = kb, traceId = trace) {
  return { params: Promise.resolve({ knowledgeBaseId, traceId }) };
}
function descriptor(format: "json" | "csv" = "json") {
  return {
    filename: `${filename}.${format}`,
    media_type: format === "json" ? "application/json" : "text/csv",
    content: format === "json"
      ? JSON.stringify({
          schema_version: 1,
          artifact_type: "retrieval_trace",
          source: { id: trace, knowledge_base_id: kb },
          configuration: { top_k: 5 },
          metrics: { duration_ms: 2.1 },
          results: [],
        })
      : "schema_version,artifact_type,record_count\r\n1,retrieval_trace,0\r\n",
  };
}

describe("SP-26 scoped trace downloads", () => {
  beforeEach(() => {
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockReset();
    mocks.backendRequest.mockResolvedValue({ status: 200, payload: descriptor() });
  });

  it("authenticates and returns safe JSON attachment with expected content", async () => {
    const response = await GET(request(), context());
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toContain("no-store");
    expect(response.headers.get("Content-Disposition")).toBe(
      `attachment; filename="${filename}.json"`,
    );
    expect(response.headers.get("Content-Type")).toContain("application/json");
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect((await response.json()).configuration.top_k).toBe(5);
    expect(mocks.backendRequest).toHaveBeenCalledWith(
      `/knowledge-bases/${kb}/retrieval/traces/${trace}/export?format=json`,
    );
  });

  it("returns a native CSV attachment, never a JSON wrapper", async () => {
    mocks.backendRequest.mockResolvedValueOnce({ status: 200, payload: descriptor("csv") });
    const response = await GET(request("format=csv"), context());
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toContain("text/csv");
    expect(response.headers.get("Content-Disposition")).toContain(`${filename}.csv`);
    expect(await response.text()).toContain("1,retrieval_trace,0");
  });

  it("rejects missing sessions, invalid IDs, extra query params and invalid formats", async () => {
    mocks.authFailure.mockReturnValueOnce(
      NextResponse.json({ error: "Operator sign-in required." }, { status: 401 }),
    );
    expect((await GET(request(), context())).status).toBe(401);
    expect((await GET(request(), context("not-a-uuid"))).status).toBe(400);
    expect((await GET(request(), context(kb, "bad-id"))).status).toBe(400);
    expect((await GET(request("format=zip"), context())).status).toBe(422);
    expect((await GET(request("format=json&format=csv"), context())).status).toBe(422);
    expect((await GET(request("format=json&url=https://evil.example"), context())).status).toBe(422);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("rejects invented source IDs, attachment names, and bad content", async () => {
    mocks.backendRequest.mockResolvedValueOnce({
      status: 200,
      payload: { ...descriptor(), filename: "not-expected.json" },
    });
    expect((await GET(request(), context())).status).toBe(502);

    mocks.backendRequest.mockResolvedValueOnce({
      status: 200,
      payload: { ...descriptor(), content: JSON.stringify({ ...JSON.parse(descriptor().content), source: { id: trace, knowledge_base_id: "other" } }) },
    });
    expect((await GET(request(), context())).status).toBe(502);
  });

  it("sanitizes upstream errors", async () => {
    mocks.backendRequest.mockRejectedValueOnce(new Error("secret provider key"));
    const response = await GET(request(), context());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "Backend temporarily unavailable." });
  });
});
