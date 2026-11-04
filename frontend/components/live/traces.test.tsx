import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveTraceHistoryPage } from "./traces";

const toast = vi.hoisted(() => ({ notify: vi.fn() }));
vi.mock("@/components/workbench-shell", () => ({ useDemoToast: () => toast.notify }));

const kb = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const first = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const second = "3f7358dd-47f8-4dda-8284-3797e9045b8a";
const doc = "f30ecec9-f12f-480c-9002-7f83822544c1";
const chunk1 = "f10f0b5e-5765-41da-9287-b34992d38396";
const chunk2 = "c89b74bb-ad22-44c5-a4bc-3d1493635a70";

const summary1 = {
  id: first,
  mode: "keyword",
  query: "retention policy",
  top_k: 5,
  candidate_k: null,
  rrf_k: null,
  duration_ms: 12.4,
  stage_timings_ms: { keyword_search: 7.4 },
  embedding_provider: null,
  embedding_model: null,
  embedding_dimensions: null,
  result_count: 1,
  created_at: "2026-11-03T18:00:00Z",
};
const summary2 = {
  id: second,
  mode: "keyword",
  query: "retention policy",
  top_k: 5,
  candidate_k: null,
  rrf_k: null,
  duration_ms: 8.2,
  stage_timings_ms: null,
  embedding_provider: null,
  embedding_model: null,
  embedding_dimensions: null,
  result_count: 2,
  created_at: "2026-11-03T17:00:00Z",
};
const prefix = `/api/workspace/knowledge-bases/${kb}/retrieval`;
const evidence = {
  rank: 1,
  chunk_id: chunk1,
  document_id: doc,
  chunk_index: 0,
  text: "The real record is immutable.",
  start_offset: 30,
  end_offset: 59,
  cosine_similarity: null,
  keyword_score: 0.07234,
  rrf_score: null,
  vector_rank: null,
  keyword_rank: null,
};
const comparison = {
  first: {
    trace_id: first,
    mode: "keyword",
    query: "retention policy",
    top_k: 5,
    candidate_k: null,
    rrf_k: null,
    duration_ms: 12.4,
    stage_timings_ms: { keyword_search: 7.4 },
    embedding_provider: null,
    embedding_model: null,
    embedding_dimensions: null,
    result_count: 1,
  },
  second: {
    trace_id: second,
    mode: "keyword",
    query: "retention policy",
    top_k: 5,
    candidate_k: null,
    rrf_k: null,
    duration_ms: 8.2,
    stage_timings_ms: null,
    embedding_provider: null,
    embedding_model: null,
    embedding_dimensions: null,
    result_count: 2,
  },
  same_query: true,
  overlap_count: 1,
  union_count: 2,
  overlap_ratio: 0.5,
  first_only_count: 0,
  second_only_count: 1,
  duration_delta_ms: -4.2,
  results: [
    {
      chunk_id: chunk1,
      document_id: doc,
      chunk_index: 0,
      text: "The real record is immutable.",
      start_offset: 30,
      end_offset: 59,
      first_rank: 1,
      second_rank: 2,
      rank_delta: 1,
      first_cosine_similarity: null,
      second_cosine_similarity: null,
      first_keyword_score: 0.07234,
      second_keyword_score: 0.064,
      first_rrf_score: null,
      second_rrf_score: null,
    },
    {
      chunk_id: chunk2,
      document_id: doc,
      chunk_index: 1,
      text: "The newly added source was also found.",
      start_offset: 80,
      end_offset: 117,
      first_rank: null,
      second_rank: 1,
      rank_delta: null,
      first_cosine_similarity: null,
      second_cosine_similarity: null,
      first_keyword_score: null,
      second_keyword_score: 0.1,
      first_rrf_score: null,
      second_rrf_score: null,
    },
  ],
};

let empty = false;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url === "/api/workspace/knowledge-bases?offset=0") {
    return Promise.resolve(
      json({ items: [{ id: kb, name: "Engineering sources" }], limit: 50, offset: 0 }),
    );
  }
  if (url === prefix + "/traces?offset=0") {
    return Promise.resolve(
      json({ items: empty ? [] : [summary1, summary2], limit: 50, offset: 0 }),
    );
  }
  if (url === prefix + "/traces/" + first) {
    return Promise.resolve(
      json({
        ...summary1,
        knowledge_base_id: kb,
        results: [evidence],
      }),
    );
  }
  if (url === prefix + "/trace-comparisons" && init?.method === "POST") {
    return Promise.resolve(json(comparison));
  }
  return Promise.resolve(json({ error: "Unexpected path " + url }, 500));
}

describe("live persisted trace history", () => {
  beforeEach(() => {
    empty = false;
    toast.notify.mockClear();
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("loads real history without triggering model queries or implicit comparisons", async () => {
    render(<LiveTraceHistoryPage />);
    await screen.findByRole("option", { name: "Engineering sources" });
    await screen.findByRole("combobox", { name: "Trace B · comparison" });
    expect(screen.getByText("Trace history")).toBeInTheDocument();
    expect(screen.getAllByText(/12.4 ms/).length).toBeGreaterThan(0);
    expect(screen.getByText("Compare two saved retrievals")).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([, options]) => options?.method === "POST")).toBe(
      false,
    );
  });

  it("opens the original evidence snapshot without rerunning retrieval", async () => {
    render(<LiveTraceHistoryPage />);
    await screen.findByRole("button", { name: /View saved evidence/i });
    fireEvent.click(screen.getByRole("button", { name: /View saved evidence/i }));
    expect(await screen.findByText("The real record is immutable.")).toBeInTheDocument();
    expect(screen.getByText(/Raw Postgres FTS: 0.07234/)).toBeInTheDocument();
    expect(screen.getByText("Keyword search")).toBeInTheDocument();
    expect(screen.getByText("7.4 ms")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inspect original document" })).toHaveAttribute(
      "href",
      `/chunks?kb=${kb}&doc=${doc}`,
    );
    expect(
      vi.mocked(fetch).mock.calls.filter(([, options]) => options?.method === "POST"),
    ).toHaveLength(0);
  });

  it("compares a selected pair with true backend overlap, ranks and timing", async () => {
    render(<LiveTraceHistoryPage />);
    const select = await screen.findByRole("combobox", { name: "Trace B · comparison" });
    fireEvent.change(select, { target: { value: second } });
    fireEvent.click(screen.getByRole("button", { name: "Compare saved traces" }));
    expect(await screen.findByText("50.0%")).toBeInTheDocument();
    expect(screen.getByText(/Down 1/)).toBeInTheDocument();
    expect(screen.getByText(/Only in B/)).toBeInTheDocument();
    expect(screen.getByText(/-4.2 ms/)).toBeInTheDocument();
    expect(screen.getByText(/A 7.4 ms \/ B Not recorded/)).toBeInTheDocument();
    expect(screen.getByText(/Δ not available/)).toBeInTheDocument();
    const call = vi
      .mocked(fetch)
      .mock.calls.find(([path]) => String(path) === prefix + "/trace-comparisons");
    expect(call?.[1]).toMatchObject({
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      first_trace_id: first,
      second_trace_id: second,
    });
  });

  it("filters loaded traces by mode and warns when the backend compares different queries", async () => {
    const replacement = structuredClone(comparison);
    replacement.same_query = false;
    replacement.second.query = "different query";
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
        String(input).endsWith("/trace-comparisons")
          ? Promise.resolve(json(replacement))
          : fakeFetch(input, init),
      ),
    );
    render(<LiveTraceHistoryPage />);
    const select = await screen.findByRole("combobox", { name: "Trace B · comparison" });
    fireEvent.change(select, { target: { value: second } });
    fireEvent.click(screen.getByRole("button", { name: "Compare saved traces" }));
    expect(await screen.findByText(/Different queries: overlap/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Filter retrieval mode" }), {
      target: { value: "vector" },
    });
    expect(screen.getByText("No loaded traces match")).toBeInTheDocument();
  });

  it("shows an honest empty state and a way to create saved traces", async () => {
    empty = true;
    render(<LiveTraceHistoryPage />);
    expect(await screen.findByText("No saved retrievals")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link", { name: "Run a query" })
        .some((link) => link.getAttribute("href") === `/retrieval?kb=${kb}`),
    ).toBe(true);
    expect(screen.queryByRole("button", { name: "Compare saved traces" })).not.toBeInTheDocument();
  });
});
