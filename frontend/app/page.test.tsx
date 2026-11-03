import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "./page";

const kbA = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const kbB = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const docA = "3f7358dd-47f8-4dda-8284-3797e9045b8a";
const docB = "f30ecec9-f12f-480c-9002-7f83822544c1";
const trace = "f10f0b5e-5765-41da-9287-b34992d38396";
const dataset = "c89b74bb-ad22-44c5-a4bc-3d1493635a70";

let emptyWorkspace = false;
let unauthorized = false;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function page(items: unknown[]): unknown {
  return { items, limit: 50, offset: 0 };
}

function fakeFetch(input: RequestInfo | URL): Promise<Response> {
  const url = String(input);
  if (url === "/api/workspace/knowledge-bases?offset=0") {
    if (unauthorized) return Promise.resolve(json({ error: "Operator sign-in required." }, 401));
    return Promise.resolve(
      json(
        page(
          emptyWorkspace
            ? []
            : [
                { id: kbA, name: "Employee policies", created_at: "2026-11-03T10:00:00Z" },
                { id: kbB, name: "Product notes", created_at: "2026-11-03T11:00:00Z" },
              ],
        ),
      ),
    );
  }
  if (url === `/api/workspace/knowledge-bases/${kbA}/documents?offset=0`) {
    return Promise.resolve(
      json(
        page([
          {
            id: docA,
            knowledge_base_id: kbA,
            filename: "operations-policy.md",
            active_chunk_version: 2,
            created_at: "2026-11-03T12:00:00Z",
          },
          {
            id: docB,
            knowledge_base_id: kbA,
            filename: "draft-handbook.md",
            active_chunk_version: 0,
            created_at: "2026-11-03T13:00:00Z",
          },
        ]),
      ),
    );
  }
  if (url === `/api/workspace/knowledge-bases/${kbB}/documents?offset=0`) {
    return Promise.resolve(
      json(
        page([
          {
            id: docB,
            knowledge_base_id: kbB,
            filename: "product-guide.txt",
            active_chunk_version: 1,
            created_at: "2026-11-03T14:00:00Z",
          },
        ]),
      ),
    );
  }
  if (url === `/api/workspace/knowledge-bases/${kbA}/retrieval/traces?offset=0`) {
    return Promise.resolve(
      json(
        page([
          {
            id: trace,
            query: "real retention policy",
            mode: "keyword",
            top_k: 10,
            duration_ms: 18.4,
            result_count: 2,
            created_at: "2026-11-03T15:00:00Z",
          },
        ]),
      ),
    );
  }
  if (url === `/api/workspace/knowledge-bases/${kbB}/retrieval/traces?offset=0`) {
    return Promise.resolve(json(page([])));
  }
  if (url === `/api/workspace/knowledge-bases/${kbA}/evaluation-datasets?offset=0`) {
    return Promise.resolve(
      json(page([{ id: dataset, name: "Policy QA", knowledge_base_id: kbA, case_count: 3 }])),
    );
  }
  if (url === `/api/workspace/knowledge-bases/${kbB}/evaluation-datasets?offset=0`) {
    return Promise.resolve(json(page([])));
  }
  if (
    url === `/api/workspace/knowledge-bases/${kbA}/evaluation-datasets/${dataset}/runs?offset=0`
  ) {
    return Promise.resolve(
      json(
        page([
          {
            run_id: "b71a0d37-637d-4f55-9749-40d6d1c2b953",
            dataset_id: dataset,
            mode: "keyword",
            top_k: 10,
            case_count: 3,
            mean_recall_at_k: 0.8,
            mean_precision_at_k: 0.5,
            mrr_at_k: 0.7,
            mean_ndcg_at_k: 0.9,
            mean_judgment_coverage_at_k: 1,
            mean_duration_ms: 16,
            created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          },
        ]),
      ),
    );
  }
  return Promise.resolve(json({ error: "Unexpected request: " + url }, 500));
}

describe("Spurel live Overview", () => {
  beforeEach(() => {
    emptyWorkspace = false;
    unauthorized = false;
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows real scoped documents, saved retrievals and benchmark metrics without implicit model calls", async () => {
    render(<Home />);
    await screen.findByText("operations-policy.md");
    expect(
      screen.getByRole("heading", { name: "Every retrieval decision. Visible." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Stop guessing why RAG works." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Live FastAPI / PostgreSQL")).toBeInTheDocument();
    expect(screen.getByText("real retention policy")).toBeInTheDocument();
    expect(await screen.findByText("80.0%")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Retrieval quality over time" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: /Measured recall and precision over the last 7 days from 1 saved benchmark/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("18.4 ms")).toBeInTheDocument();
    const indexedCard = screen.getByText("Indexed documents").closest(".metric-card");
    expect(indexedCard).not.toBeNull();
    expect(within(indexedCard as HTMLElement).getByText("1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /real retention policy/ })).toHaveAttribute(
      "href",
      `/traces?kb=${kbA}&trace=${trace}`,
    );
    expect(screen.getByRole("link", { name: /Explore retrieval lab/i })).toHaveAttribute(
      "href",
      `/retrieval?kb=${kbA}`,
    );
    expect(screen.queryByText("91.8%")).not.toBeInTheDocument();
    expect(screen.queryByText("18.4k")).not.toBeInTheDocument();
    expect(
      vi.mocked(fetch).mock.calls.every(([, init]) => !init?.method || init.method === "GET"),
    ).toBe(true);
  });

  it("switches knowledge-base scope without mixing history or evaluation results", async () => {
    render(<Home />);
    await screen.findByText("operations-policy.md");
    fireEvent.change(screen.getByRole("combobox", { name: "Knowledge base" }), {
      target: { value: kbB },
    });
    await screen.findByText("product-guide.txt");
    expect(screen.getByText("No retrieval traces")).toBeInTheDocument();
    expect(screen.getByText("No evaluation datasets")).toBeInTheDocument();
    expect(screen.getByText("No evaluation dataset")).toBeInTheDocument();
    expect(screen.queryByText("real retention policy")).not.toBeInTheDocument();
    expect(screen.queryByText("80.0%")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Generate a RAG answer/ })).toHaveAttribute(
      "href",
      `/rag?kb=${kbB}`,
    );
  });

  it("has an honest empty state for a new workspace", async () => {
    emptyWorkspace = true;
    render(<Home />);
    expect(await screen.findByText("No knowledge bases yet")).toBeInTheDocument();
    expect(screen.queryByText("real retention policy")).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls).toHaveLength(1);
  });

  it("prompts for operator sign-in without loading protected source data", async () => {
    unauthorized = true;
    render(<Home />);
    expect(await screen.findByRole("link", { name: /Sign in as local operator/ })).toHaveAttribute(
      "href",
      "/operator/login",
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/session has expired/i);
    await waitFor(() => expect(vi.mocked(fetch).mock.calls).toHaveLength(1));
  });
});
