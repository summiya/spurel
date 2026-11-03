import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveRagAnswersPage } from "./rag-answers";

const toast = vi.hoisted(() => ({ notify: vi.fn() }));
vi.mock("@/components/workbench-shell", () => ({
  useDemoToast: () => toast.notify,
}));

const kb = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const traceId = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const docId = "3f7358dd-47f8-4dda-8284-3797e9045b8a";
const chunkId = "f10f0b5e-5765-41da-9287-b34992d38396";
const endpoint = `/api/workspace/knowledge-bases/${kb}/rag/answer`;

const grounded = {
  trace_id: traceId,
  answer: "Employees receive 30 days of leave [S1]. Unknown supporting label [S4].",
  retrieved_chunk_count: 1,
  generation_provider: "openai",
  generation_model: "gpt-test",
  sources: [
    {
      label: "S1",
      retrieval_rank: 1,
      chunk_id: chunkId,
      document_id: docId,
      chunk_index: 2,
      excerpt: "The company grants 30 days of annual leave after one year.",
      start_offset: 100,
      end_offset: 158,
      page_start: 2,
      page_end: 2,
      ocr_used: true,
    },
  ],
};
const noContext = {
  trace_id: traceId,
  answer: "I couldn't find enough information in the knowledge base to answer that question.",
  retrieved_chunk_count: 0,
  generation_provider: null,
  generation_model: null,
  sources: [],
};

let response: unknown = grounded;
let responseCode = 200;
let noBases = false;

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
      json({
        items: noBases ? [] : [{ id: kb, name: "Employee handbook" }],
        limit: 50,
        offset: 0,
      }),
    );
  }
  if (url === endpoint && init?.method === "POST")
    return Promise.resolve(json(response, responseCode));
  return Promise.resolve(json({ error: "Unexpected test path: " + url }, 500));
}

function ask() {
  fireEvent.change(screen.getByRole("textbox", { name: "Question" }), {
    target: { value: "How many leave days do employees receive?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate live answer" }));
}

describe("SP-15 live RAG answer frontend", () => {
  beforeEach(() => {
    response = grounded;
    responseCode = 200;
    noBases = false;
    toast.notify.mockClear();
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("loads real knowledge bases but makes no automatic OpenAI calls", async () => {
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    expect(screen.getByText("No live answer yet")).toBeInTheDocument();
    expect(screen.getByText("Live FastAPI RAG")).toBeInTheDocument();
    expect(screen.queryByText(/sample refund policy/i)).not.toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET"),
    ).toBe(true);
    expect(window.confirm).not.toHaveBeenCalled();
  });

  it("does not dispatch generation if the user rejects the cost warning", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => false),
    );
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();
    expect(window.confirm).toHaveBeenCalledOnce();
    expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("submits a validated request and shows exact sources with clickable citation and trace links", async () => {
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();

    expect(await screen.findByRole("button", { name: "Inspect source S1" })).toBeInTheDocument();
    expect(
      screen.getByText("The company grants 30 days of annual leave after one year."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Inspect saved retrieval trace/ })).toHaveAttribute(
      "href",
      `/traces?kb=${kb}&trace=${traceId}`,
    );
    expect(screen.getByRole("link", { name: /Inspect original document/ })).toHaveAttribute(
      "href",
      `/chunks?kb=${kb}&doc=${docId}`,
    );
    expect(screen.queryByRole("button", { name: "Inspect source S4" })).not.toBeInTheDocument();
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url) === endpoint);
    expect(call?.[1]).toMatchObject({
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      query: "How many leave days do employees receive?",
      top_k: 8,
      candidate_k: 50,
      rrf_k: 60,
    });
    expect(screen.getByText(/not independently verified claim citations/i)).toBeInTheDocument();
    expect(screen.getByText(/PDF page 2 · includes OCR text/)).toBeInTheDocument();
  });

  it("distinguishes no matching context from model-generated answers", async () => {
    response = noContext;
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();
    expect(await screen.findByText("No source excerpts")).toBeInTheDocument();
    expect(screen.getByText(/backend skipped text generation/i)).toBeInTheDocument();
    expect(screen.getByText("Not used")).toBeInTheDocument();
    expect(screen.getByText(/couldn't find enough information/)).toBeInTheDocument();
  });

  it("rejects malformed responses instead of displaying fabricated source attribution", async () => {
    response = { ...grounded, sources: [{ ...grounded.sources[0], chunk_id: "not-a-uuid" }] };
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid evidence response/i);
    expect(
      screen.queryByRole("link", { name: /Inspect original document/ }),
    ).not.toBeInTheDocument();
  });

  it("surfaces unavailable generation providers without inserting a demo response", async () => {
    responseCode = 503;
    response = { error: "RAG service temporarily unavailable" };
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /RAG service temporarily unavailable/i,
    );
    expect(screen.queryByText(/30 days of leave \[S1\]/i)).not.toBeInTheDocument();
  });

  it("keeps saved results tied to the submitted settings, not newly edited form fields", async () => {
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    ask();
    await screen.findByRole("button", { name: "Inspect source S1" });
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), {
      target: { value: "A different question" },
    });
    expect(
      screen.getByText(/answer below belongs to the previous submitted request/i),
    ).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(
      1,
    );
  });

  it("provides a clear empty state when there is no knowledge base", async () => {
    noBases = true;
    render(<LiveRagAnswersPage />);
    await screen.findByText("No knowledge bases yet");
    expect(screen.queryByRole("button", { name: "Generate live answer" })).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.every(([, init]) => init?.method !== "POST")).toBe(true);
  });

  it("does not execute with invalid client settings", async () => {
    render(<LiveRagAnswersPage />);
    await screen.findByRole("option", { name: "Employee handbook" });
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), {
      target: { value: "Policy?" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: /Candidate K/ }), {
      target: { value: "2" },
    });
    expect(screen.getByRole("button", { name: "Generate live answer" })).toBeDisabled();
    await waitFor(() => expect(window.confirm).not.toHaveBeenCalled());
  });
});
