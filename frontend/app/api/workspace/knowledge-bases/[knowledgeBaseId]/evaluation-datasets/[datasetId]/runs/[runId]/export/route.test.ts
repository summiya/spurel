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
const dataset = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const run = "c89b74bb-ad22-44c5-a4bc-3d1493635a70";

const url = `http://localhost:3000/api/workspace/knowledge-bases/${kb}/evaluation-datasets/${dataset}/runs/${run}/export?format=json`;
function request(value = url) { return new NextRequest(value); }
function context(knowledgeBaseId = kb, datasetId = dataset, runId = run) {
  return { params: Promise.resolve({ knowledgeBaseId, datasetId, runId }) };
}
function descriptor() {
  return {
    filename: `spurel-evaluation-run-${run}.json`,
    media_type: "application/json",
    content: JSON.stringify({
      schema_version: 1,
      artifact_type: "evaluation_run",
      source: { run_id: run, knowledge_base_id: kb, dataset_id: dataset },
      configuration: { mode: "keyword", top_k: 10 },
      metrics: { mean_recall_at_k: 0.5 },
      cases: [{ query: "Saved evaluation question" }],
    }),
  };
}

describe("SP-26 saved evaluation export proxy", () => {
  beforeEach(() => {
    mocks.backendRequest.mockReset();
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockResolvedValue({ status: 200, payload: descriptor() });
  });
  it("keeps scoped, measured run metrics in a secure download", async () => {
    const response = await GET(request(), context());
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Disposition")).toContain(`spurel-evaluation-run-${run}.json`);
    expect(response.headers.get("Cache-Control")).toContain("no-store");
    expect((await response.json()).metrics.mean_recall_at_k).toBe(0.5);
    expect(mocks.backendRequest).toHaveBeenCalledWith(
      `/knowledge-bases/${kb}/evaluation-datasets/${dataset}/runs/${run}/export?format=json`,
    );
  });
  it("does not request upstream for unauthenticated, malformed or cross-scope URLs", async () => {
    mocks.authFailure.mockReturnValueOnce(NextResponse.json({ error: "No session" }, { status: 401 }));
    expect((await GET(request(), context())).status).toBe(401);
    expect((await GET(request(), context(kb, "bad-dataset"))).status).toBe(400);
    expect((await GET(request(), context("bad-kb"))).status).toBe(400);
    expect((await GET(request(), context(kb, dataset, "bad-run"))).status).toBe(400);
    expect((await GET(request(url.replace("format=json", "format=xml")), context())).status).toBe(422);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });
  it("rejects a response from another dataset and masks provider errors", async () => {
    mocks.backendRequest.mockResolvedValueOnce({
      status: 200,
      payload: { ...descriptor(), content: descriptor().content.replace(dataset, "untrusted") },
    });
    expect((await GET(request(), context())).status).toBe(502);
    mocks.backendRequest.mockRejectedValueOnce(new Error("database secret"));
    expect((await GET(request(), context())).status).toBe(503);
  });
});
