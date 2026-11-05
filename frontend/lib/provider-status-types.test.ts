import { describe, expect, it } from "vitest";

import { isProviderStatus, providerName } from "./provider-status-types";

const good = {
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

describe("SP-25 credentials-free provider status", () => {
  it("accepts real, bounded provider identity without host or secrets", () => {
    expect(isProviderStatus(good)).toBe(true);
    expect(providerName("ollama")).toBe("Ollama (local)");
    expect(providerName("openai")).toBe("OpenAI");
  });

  it("rejects impossible dimensions and unrecognized providers", () => {
    expect(isProviderStatus({ ...good, embedding: { ...good.embedding, dimensions: 0 } })).toBe(
      false,
    );
    expect(isProviderStatus({ ...good, generation: { ...good.generation, provider: "admin" } })).toBe(
      false,
    );
    expect(
      isProviderStatus({ ...good, embedding: { ...good.embedding, configured: "yes" } }),
    ).toBe(false);
    expect(isProviderStatus(null)).toBe(false);
  });
});
