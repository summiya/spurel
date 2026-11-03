import { describe, expect, it, vi } from "vitest";

import { isPage, liveError, WorkspaceError, workspaceFetch } from "./live-client";

describe("workspace request handling", () => {
  it("uses same-origin cookies and disables caching", async () => {
    const backend = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], offset: 0, limit: 50 }), { status: 200 }),
    );
    vi.stubGlobal("fetch", backend);
    try {
      const page = await workspaceFetch<{ items: []; offset: number; limit: number }>(
        "/api/workspace/knowledge-bases",
      );
      expect(isPage(page)).toBe(true);
      expect(backend.mock.calls[0][1]).toMatchObject({
        cache: "no-store",
        credentials: "same-origin",
      });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("shows sign-in guidance for expired sessions and rejects invalid payloads", () => {
    expect(liveError(new WorkspaceError(401, "Expired"))).toContain("Sign in again");
    expect(isPage({ items: "not an array", offset: 0, limit: 50 })).toBe(false);
  });
});
