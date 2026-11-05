import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

const mocks = vi.hoisted(() => ({
  authFailure: vi.fn(),
  backendRequest: vi.fn(),
}));

vi.mock("@/lib/server/backend-client", () => ({
  backendRequest: mocks.backendRequest,
  safeBackendError: () => ({ status: 503, error: "Backend temporarily unavailable." }),
}));

vi.mock("@/lib/server/operator-session", () => ({
  authFailure: mocks.authFailure,
  noStore: (result: NextResponse) => {
    result.headers.set("Cache-Control", "no-store");
    return result;
  },
}));

function request(): NextRequest {
  return new NextRequest("http://localhost:3000/api/workspace/providers/status");
}

describe("SP-25 provider metadata route", () => {
  beforeEach(() => {
    mocks.backendRequest.mockReset();
    mocks.authFailure.mockReset();
    mocks.authFailure.mockReturnValue(null);
    mocks.backendRequest.mockResolvedValue({
      status: 200,
      payload: {
        embedding: { provider: "openai", model: "test", configured: true, dimensions: 1536 },
        generation: { provider: "ollama", model: "local", configured: true, dimensions: null },
      },
    });
  });

  it("forwards only a fixed protected GET, without keys or arbitrary paths", async () => {
    const response = await GET(request());
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(mocks.backendRequest).toHaveBeenCalledWith("/providers/status");
    expect(mocks.authFailure).toHaveBeenCalledWith(expect.any(NextRequest));
    const body = await response.json();
    expect(body.embedding.provider).toBe("openai");
  });

  it("denies unauthenticated status reads", async () => {
    mocks.authFailure.mockReturnValueOnce(NextResponse.json({ error: "Sign in" }, { status: 401 }));
    expect((await GET(request())).status).toBe(401);
    expect(mocks.backendRequest).not.toHaveBeenCalled();
  });

  it("sanitizes upstream errors", async () => {
    mocks.backendRequest.mockRejectedValueOnce(new Error("API secret"));
    const response = await GET(request());
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "Backend temporarily unavailable." });
  });
});
