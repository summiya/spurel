import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderStatusPanel } from "./provider-status";

const result = {
  embedding: {
    provider: "ollama",
    model: "nomic-embed-text",
    dimensions: 768,
    configured: true,
  },
  generation: {
    provider: "openai_compatible",
    model: "hosted-chat",
    dimensions: null,
    configured: true,
  },
};

describe("read-only provider configuration in workbench", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows selected backend identities without sending provider keys or initiating inference", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(result), { status: 200 })),
    );
    render(<ProviderStatusPanel purpose="both" />);
    expect(await screen.findByText(/Ollama \(local\) · nomic-embed-text/)).toBeInTheDocument();
    expect(screen.getByText(/OpenAI-compatible endpoint · hosted-chat/)).toBeInTheDocument();
    expect(screen.getByText(/reprocessing documents/)).toBeInTheDocument();
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/workspace/providers/status");
    expect(vi.mocked(fetch).mock.calls[0][1]).toMatchObject({
      cache: "no-store",
      credentials: "same-origin",
    });
  });

  it("shows configuration missing without guessing provider availability", async () => {
    const unconfigured = {
      ...result,
      embedding: { ...result.embedding, configured: false, model: null, dimensions: null },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(unconfigured), { status: 200 })),
    );
    render(<ProviderStatusPanel purpose="embedding" />);
    expect(await screen.findByText(/Needs server configuration/)).toBeInTheDocument();
    expect(screen.queryByText(/hosted-chat/)).not.toBeInTheDocument();
  });

  it("does not invent provider information after an upstream failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 503 })));
    render(<ProviderStatusPanel purpose="generation" />);
    expect(await screen.findByText(/Provider configuration details are unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/hosted-chat/)).not.toBeInTheDocument();
  });
});
