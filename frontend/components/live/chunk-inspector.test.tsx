import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LiveChunkInspectorPage } from "./chunk-inspector";

vi.mock("@/components/workbench-shell", () => ({
  useDemoToast: () => vi.fn(),
}));

const kb1 = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const doc1 = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const doc2 = "171e74ab-2229-4f2a-a6e8-85c8f4f2a1fb";

const bases = [{ id: kb1, name: "Engineering docs", created_at: "2026-11-03T10:00:00Z" }];

const docs = [
  {
    id: doc1,
    knowledge_base_id: kb1,
    filename: "authentication.md",
    media_type: "text/markdown",
    size_bytes: 220,
    created_at: "2026-11-03T10:00:00Z",
    active_chunk_version: 2,
  },
  {
    id: doc2,
    knowledge_base_id: kb1,
    filename: "unindexed.txt",
    media_type: "text/plain",
    size_bytes: 44,
    created_at: "2026-11-03T11:00:00Z",
    active_chunk_version: 0,
  },
];

const versions = [
  {
    version: 2,
    chunk_count: 2,
    created_at: "2026-11-03T12:00:00Z",
    is_active: true,
    status: "ready",
    attempt_count: 1,
  },
  {
    version: 1,
    chunk_count: 1,
    created_at: "2026-11-02T12:00:00Z",
    is_active: false,
    status: "ready",
    attempt_count: 1,
  },
];

const activeChunks = [
  {
    id: "8e8278f2-9ec3-4d6c-b273-52e04f02cb26",
    document_id: doc1,
    index: 0,
    text: "Current live excerpt:\nNever reuse a login challenge.",
    start_offset: 120,
    end_offset: 170,
    has_embeddings: true,
    embedding_count: 2,
  },
  {
    id: "6c92bd03-bba3-44f0-a7d0-b17e5728c590",
    document_id: doc1,
    index: 1,
    text: "Next chunk from a real stored version.",
    start_offset: 160,
    end_offset: 198,
    has_embeddings: false,
    embedding_count: 0,
  },
];
const oldChunks = [
  {
    ...activeChunks[0],
    id: "d458b2d6-9cc0-4fb1-9cc0-02dc0ffde831",
    text: "Old source excerpt: login via password.",
    start_offset: 80,
    end_offset: 118,
    embedding_count: 1,
  },
];

function response(items: unknown[], offset = 0) {
  return new Response(JSON.stringify({ items, limit: 50, offset }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeFetch(input: RequestInfo | URL): Promise<Response> {
  const path = String(input);
  if (path === "/api/workspace/knowledge-bases?offset=0") return Promise.resolve(response(bases));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents?offset=0`)
    return Promise.resolve(response(docs));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents/${doc1}/versions?offset=0`)
    return Promise.resolve(response(versions));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents/${doc1}/chunks?offset=0`)
    return Promise.resolve(response(activeChunks));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents/${doc1}/chunks?version=1&offset=0`)
    return Promise.resolve(response(oldChunks));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents/${doc2}/versions?offset=0`)
    return Promise.resolve(response([]));
  if (path === `/api/workspace/knowledge-bases/${kb1}/documents/${doc2}/chunks?offset=0`)
    return Promise.resolve(response([]));
  return Promise.resolve(
    new Response(JSON.stringify({ error: "Unexpected test path: " + path }), { status: 500 }),
  );
}

describe("live chunk inspector", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads real stored chunks, exact offsets, embedding counts and version status", async () => {
    render(<LiveChunkInspectorPage />);
    expect(await screen.findAllByText(/Current live excerpt/)).toBeInTheDocument();
    expect(screen.getByText(/Source offsets 120–170/)).toBeInTheDocument();
    expect(screen.getByText(/2 embeddings/)).toBeInTheDocument();
    expect(screen.getByText(/No embeddings/)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Chunk set to inspect" })).toHaveValue("active");
    expect(screen.getByText(/Active v2/)).toBeInTheDocument();
    expect(screen.queryByText("security-guidelines.md")).not.toBeInTheDocument();
  });

  it("loads historical chunks through a pinned version and never labels them active", async () => {
    render(<LiveChunkInspectorPage initialKnowledgeBaseId={kb1} initialDocumentId={doc1} />);
    await screen.findAllByText(/Current live excerpt/);
    fireEvent.change(screen.getByRole("combobox", { name: "Chunk set to inspect" }), {
      target: { value: "v:1" },
    });
    expect(await screen.findAllByText(/Old source excerpt/)).toBeInTheDocument();
    expect(screen.getByText(/Historical version 1 is read-only/)).toBeInTheDocument();
    expect(screen.getByText(/Source offsets 80–118/)).toBeInTheDocument();
    expect(screen.queryAllByText(/Current live excerpt/)).toHaveLength(0);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      `/api/workspace/knowledge-bases/${kb1}/documents/${doc1}/chunks?version=1&offset=0`,
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("shows unindexed documents without inventing an index", async () => {
    render(<LiveChunkInspectorPage />);
    await screen.findAllByText(/Current live excerpt/);
    fireEvent.click(screen.getByRole("button", { name: /unindexed.txt/ }));
    expect(await screen.findByText("No chunks in this selection")).toBeInTheDocument();
    expect(screen.getByText(/not published an active chunk set/)).toBeInTheDocument();
    expect(screen.queryAllByText(/Current live excerpt/)).toHaveLength(0);
  });

  it("filters only loaded excerpts and keeps their original source IDs", async () => {
    render(<LiveChunkInspectorPage />);
    await screen.findAllByText(/Current live excerpt/);
    fireEvent.change(screen.getByRole("searchbox", { name: /Find text or index/i }), {
      target: { value: "Next chunk" },
    });
    expect(screen.getByText(/Next chunk from a real stored version/)).toBeInTheDocument();
    const entries = document.querySelectorAll(".live-inspector-chunks .chunk-entry");
    expect(entries).toHaveLength(1);
    fireEvent.click(entries[0]);
    await waitFor(() => {
      expect(screen.getByText("6c92bd03-bba3-44f0-a7d0-b17e5728c590")).toBeInTheDocument();
    });
  });
});
