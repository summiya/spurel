import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveRetrievalLabPage } from "./retrieval-lab";

const mock = vi.hoisted(() => ({ notify: vi.fn() }));
vi.mock("@/components/workbench-shell", () => ({
  useDemoToast: () => mock.notify,
}));

const kb = {
  id: "d98d2800-9df4-4f98-a397-0d0fd19ee032",
  name: "Real engineering",
  created_at: "2026-11-03T10:00:00Z",
};
const traceId = "a55cc93b-08f4-4b83-a9ae-5a87ebc5f6ae";
const documentId = "2aeb68c9-f95d-46db-a9a3-552ce8931913";
const firstId = "b71a0d37-637d-4f55-9749-40d6d1c2b953";
const secondId = "6c92bd03-bba3-44f0-a7d0-b17e5728c590";
const base = `/api/workspace/knowledge-bases/${kb.id}/retrieval`;

const first = {
  rank: 1,
  chunk_id: firstId,
  document_id: documentId,
  chunk_index: 0,
  text: "Actual saved evidence from PostgreSQL.",
  start_offset: 120,
  end_offset: 158,
  page_start: 2,
  page_end: 3,
  ocr_used: false,
};
const second = {
  rank: 2,
  chunk_id: secondId,
  document_id: documentId,
  chunk_index: 1,
  text: "Another real chunk of indexed evidence.",
  start_offset: 150,
  end_offset: 189,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url === "/api/workspace/knowledge-bases?offset=0") {
    return Promise.resolve(json({ items: [kb], limit: 50, offset: 0 }));
  }
  if (url === `/api/workspace/knowledge-bases/${kb.id}/documents?offset=0`) {
    return Promise.resolve(
      json({
        items: [
          {
            id: documentId,
            knowledge_base_id: kb.id,
            filename: "Operations manual.pdf",
            media_type: "application/pdf",
            size_bytes: 2048,
            created_at: "2026-11-03T10:00:00Z",
            active_chunk_version: 1,
          },
        ],
        limit: 50,
        offset: 0,
      }),
    );
  }
  if (url === base + "/keyword" && init?.method === "POST") {
    const request = JSON.parse(String(init.body));
    return Promise.resolve(
      json({
        mode: "keyword",
        query: request.query,
        top_k: request.top_k,
        trace_id: traceId,
        filters: request.filters ?? null,
        duration_ms: 13.33,
        matches:
          request.query === "nothing here"
            ? []
            : [
                { ...first, keyword_score: 0.08394 },
                { ...second, keyword_score: 0.04893 },
              ],
      }),
    );
  }
  if (url === base + "/vector" && init?.method === "POST") {
    const request = JSON.parse(String(init.body));
    return Promise.resolve(
      json({
        mode: "vector",
        query: request.query,
        top_k: request.top_k,
        trace_id: traceId,
        filters: request.filters ?? null,
        duration_ms: 91.5,
        matches: [
          { ...first, cosine_similarity: 0.9321 },
          { ...second, cosine_similarity: 0.8104 },
        ],
      }),
    );
  }
  if (url === base + "/hybrid" && init?.method === "POST") {
    const request = JSON.parse(String(init.body));
    return Promise.resolve(
      json({
        mode: "hybrid",
        query: request.query,
        top_k: request.top_k,
        candidate_k: request.candidate_k,
        rrf_k: request.rrf_k,
        trace_id: traceId,
        filters: request.filters ?? null,
        duration_ms: 112.45,
        matches: [
          {
            ...first,
            rrf_score: 0.032786,
            vector_rank: 1,
            keyword_rank: 2,
            cosine_similarity: 0.9321,
            keyword_score: 0.08394,
          },
        ],
      }),
    );
  }
  if (url === base + "/traces/" + traceId) {
    return Promise.resolve(
      json({
        id: traceId,
        knowledge_base_id: kb.id,
        mode: "vector",
        query: "passwordless sessions",
        top_k: 10,
        candidate_k: null,
        rrf_k: null,
        duration_ms: 91.5,
        embedding_provider: "openai",
        embedding_model: "text-embedding-3-small",
        embedding_dimensions: 1536,
        created_at: "2026-11-03T12:00:00Z",
        results: [{ ...first, cosine_similarity: 0.9321 }],
      }),
    );
  }
  return Promise.resolve(json({ error: "Unexpected mock endpoint " + url }, 500));
}

async function ready() {
  await screen.findByRole("option", { name: "Real engineering" });
}

describe("live retrieval lab", () => {
  beforeEach(() => {
    mock.notify.mockClear();
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not issue queries automatically and defaults to free keyword mode", async () => {
    render(<LiveRetrievalLabPage />);
    await ready();
    expect(screen.getByRole("button", { name: "Keyword" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/no query-time embedding provider call/i)).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(
      0,
    );
    expect(screen.getByText("Run a query to inspect real evidence")).toBeInTheDocument();
    expect(screen.queryByText("refund-policy.md")).not.toBeInTheDocument();
  });

  it("runs an authenticated keyword request and shows raw FTS scores and trace id", async () => {
    const { container } = render(<LiveRetrievalLabPage />);
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "passwordless sessions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));

    expect(await screen.findByText(/Keyword · PostgreSQL FTS/)).toBeInTheDocument();
    expect(screen.getAllByText(/PDF page 2–3/).length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".evidence-result")).toHaveLength(2);
    expect(screen.getByText(/PostgreSQL FTS: 0.08394/)).toBeInTheDocument();
    expect(screen.getByText(/13.3 ms/)).toBeInTheDocument();
    expect(screen.getByText(/Trace ID ·/)).toHaveTextContent(traceId);
    expect(screen.getByText(/Scores are raw backend values, not percentages/)).toBeInTheDocument();

    const post = vi.mocked(fetch).mock.calls.find(([path]) => String(path) === base + "/keyword");
    expect(post?.[1]).toMatchObject({
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      query: "passwordless sessions",
      top_k: 10,
    });
    fireEvent.click(container.querySelectorAll(".evidence-result")[1]);
    expect(container.querySelectorAll(".evidence-result")[1]).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText(secondId)).toBeInTheDocument();
  });

  it("sends valid hybrid configuration and shows source ranks without fake percentages", async () => {
    const { container } = render(<LiveRetrievalLabPage />);
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "data retention" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Hybrid" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Top K (1–100)" }), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: /Candidate K/ }), {
      target: { value: "14" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: /RRF K/ }), {
      target: { value: "81" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));
    expect(await screen.findByText(/Hybrid · RRF/)).toBeInTheDocument();
    expect(container.querySelectorAll(".evidence-result")).toHaveLength(1);
    expect(screen.getByText(/RRF score: 0.032786/)).toBeInTheDocument();
    expect(screen.getByText(/Vector pool rank/)).toBeInTheDocument();
    expect(screen.getByText(/Keyword pool rank/)).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.find(([path]) => String(path) === base + "/hybrid");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      query: "data retention",
      top_k: 12,
      candidate_k: 14,
      rrf_k: 81,
    });
  });

  it("restricts search by document, type and filename without any automatic requests", async () => {
    render(<LiveRetrievalLabPage />);
    await ready();
    // The document picker loads real selected-KB documents separately from search.
    await screen.findByRole("option", { name: "Operations manual.pdf" });
    fireEvent.change(screen.getByRole("combobox", { name: "Document" }), {
      target: { value: documentId },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "File type" }), {
      target: { value: "application/pdf" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Filename contains" }), {
      target: { value: "manual" },
    });
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(
      0,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "retention" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));
    expect(await screen.findByText(/Applied document scope:/)).toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url) === base + "/keyword");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      query: "retention",
      top_k: 10,
      filters: {
        document_ids: [documentId],
        media_types: ["application/pdf"],
        filename_contains: "manual",
      },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Filename contains" }), {
      target: { value: "another" },
    });
    expect(screen.getByText(/results below belong to the last completed run/)).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(
      1,
    );
  });

  it("retrieves real vector results and can reopen their persisted trace", async () => {
    render(<LiveRetrievalLabPage />);
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "passwordless sessions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Vector" }));
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));
    expect(await screen.findByText(/Cosine similarity: 0.9321/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect saved trace" }));
    expect(await screen.findByText(/Verified persisted trace/)).toBeInTheDocument();
    expect(screen.getByText(/text-embedding-3-small/)).toBeInTheDocument();
    expect(screen.getByText(/1 saved result/)).toBeInTheDocument();
  });

  it("shows a genuine empty state for a query with no indexed matches", async () => {
    render(<LiveRetrievalLabPage />);
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "nothing here" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));
    expect(await screen.findByText("No matching indexed chunks")).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 10/)).toBeInTheDocument();
  });

  it("marks previous results stale after editing the query without making another request", async () => {
    render(<LiveRetrievalLabPage />);
    await ready();
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "passwordless sessions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run live retrieval" }));
    await screen.findByText(/Completed retrieval/);
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), {
      target: { value: "another query" },
    });
    expect(screen.getByText(/results below belong to the last completed run/)).toBeInTheDocument();
    const calls = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST");
    expect(calls).toHaveLength(1);
  });
});
