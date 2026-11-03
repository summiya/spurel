import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { LiveKnowledgeBasesPage } from "./knowledge-bases";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  notify: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh }),
}));
vi.mock("@/components/workbench-shell", () => ({
  useDemoToast: () => mocks.notify,
}));

const kb = {
  id: "d98d2800-9df4-4f98-a397-0d0fd19ee032",
  name: "Live engineering",
  created_at: "2026-11-03T10:00:00Z",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url.includes("/api/workspace/knowledge-bases?offset=")) {
    return Promise.resolve(json({ items: [kb], limit: 50, offset: 0 }));
  }
  if (url.endsWith("/documents?offset=0")) {
    return Promise.resolve(
      json({
        items: [
          {
            id: "d73b06d7-a20e-4ddf-9859-242d69d4372f",
            knowledge_base_id: kb.id,
            filename: "readme.txt",
            media_type: "text/plain",
            size_bytes: 84,
            created_at: "2026-11-03T10:00:00Z",
            active_chunk_version: 0,
          },
        ],
        limit: 50,
        offset: 0,
      }),
    );
  }
  if (url.endsWith("/process")) {
    return Promise.resolve(
      json({
        status: "processed",
        document_id: "d73b06d7-a20e-4ddf-9859-242d69d4372f",
        knowledge_base_id: kb.id,
        chunk_count: 3,
        embedded_chunk_count: 3,
        chunk_version: 1,
        reused_active_version: false,
      }),
    );
  }
  if (url === "/api/workspace/knowledge-bases" && init?.method === "POST") {
    return Promise.resolve(
      json(
        {
          id: "2b20838d-e1b5-4623-b5bf-b430bbab43f6",
          name: "Operations notes",
          created_at: "2026-11-03T11:00:00Z",
        },
        201,
      ),
    );
  }
  return Promise.resolve(json({ error: "Unexpected test request" }, 500));
}

describe("live source management", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(fakeFetch));
    mocks.replace.mockClear();
    mocks.refresh.mockClear();
    mocks.notify.mockClear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows real backend documents, not illustrative knowledge base cards", async () => {
    render(<LiveKnowledgeBasesPage />);
    await screen.findByText("readme.txt");
    expect(screen.getAllByText("Live engineering").length).toBeGreaterThan(0);
    expect(screen.queryByText("Policy library")).not.toBeInTheDocument();
    expect(screen.getByText(/Uploaded · not indexed/)).toBeInTheDocument();
    expect(screen.getByText(/actual FastAPI and PostgreSQL data/i)).toBeInTheDocument();
  });

  it("creates a collection through the authenticated same-origin route", async () => {
    render(<LiveKnowledgeBasesPage />);
    await screen.findByText("readme.txt");
    fireEvent.click(screen.getByRole("button", { name: /New knowledge base/i }));
    const dialog = screen.getByRole("dialog", { name: "New knowledge base" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: /Knowledge-base name/i }), {
      target: { value: "Operations notes" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /Create collection/i }));
    await waitFor(() => {
      expect(screen.getAllByText("Operations notes").length).toBeGreaterThan(0);
    });
    const called = vi
      .mocked(fetch)
      .mock.calls.find(
        ([path, init]) =>
          String(path) === "/api/workspace/knowledge-bases" && init?.method === "POST",
      );
    expect(called).toBeDefined();
    expect(called?.[1]?.body).toBe(JSON.stringify({ name: "Operations notes" }));
    expect(mocks.notify).toHaveBeenCalledWith("Knowledge base created in PostgreSQL.");
  });

  it("keeps legacy character settings by default and opts into token sizing explicitly", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<LiveKnowledgeBasesPage />);
    await screen.findByText("readme.txt");
    const strategy = screen.getByRole("combobox", { name: "Chunking method" });
    expect(strategy).toHaveValue("characters");
    expect(screen.getByRole("spinbutton", { name: /Chunk size/ })).toHaveValue(1000);
    fireEvent.change(strategy, { target: { value: "tokens" } });
    expect(screen.getByRole("spinbutton", { name: /Chunk size/ })).toHaveValue(512);
    expect(screen.getByRole("spinbutton", { name: /Overlap/ })).toHaveValue(64);
    fireEvent.click(screen.getByRole("button", { name: /^Process$/i }));
    await screen.findByText(/Indexed · version 1/);
    expect(window.confirm).toHaveBeenCalledOnce();
    const call = vi.mocked(fetch).mock.calls.find(([url, opts]) =>
      String(url).endsWith("/process") && opts?.method === "POST",
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      strategy: "tokens",
      chunk_size: 512,
      overlap: 64,
    });
  });

  it("does not process when the opt-in confirmation is declined", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    render(<LiveKnowledgeBasesPage />);
    await screen.findByText("readme.txt");
    fireEvent.change(screen.getByRole("combobox", { name: "Chunking method" }), {
      target: { value: "tokens" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Process$/i }));
    expect(window.confirm).toHaveBeenCalledOnce();
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith("/process")))
      .toBe(false);
  });

  it("processes a document and shows the persisted active version", async () => {
    render(<LiveKnowledgeBasesPage />);
    await screen.findByText("readme.txt");
    fireEvent.click(screen.getByRole("button", { name: /^Process$/i }));
    expect(await screen.findByText(/Indexed · version 1/)).toBeInTheDocument();
    expect(mocks.notify).toHaveBeenCalledWith("Indexed 3 chunks in version 1.");
  });
});
