/** Public, credentials-free model identities from the protected backend. */

export type ModelProvider = "openai" | "openai_compatible" | "ollama" | "invalid";

export interface ProviderState {
  provider: ModelProvider;
  model: string | null;
  configured: boolean;
  dimensions: number | null;
}

export interface ProviderStatus {
  embedding: ProviderState;
  generation: ProviderState;
}

function providerState(value: unknown): value is ProviderState {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const data = value as Record<string, unknown>;
  return (
    ["openai", "openai_compatible", "ollama", "invalid"].includes(String(data.provider)) &&
    (data.model === null ||
      (typeof data.model === "string" && data.model.length > 0 && data.model.length <= 255)) &&
    typeof data.configured === "boolean" &&
    (data.dimensions === null ||
      (typeof data.dimensions === "number" &&
        Number.isInteger(data.dimensions) &&
        data.dimensions >= 1 &&
        data.dimensions <= 16384))
  );
}

export function isProviderStatus(value: unknown): value is ProviderStatus {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const data = value as Record<string, unknown>;
  return providerState(data.embedding) && providerState(data.generation);
}

export function providerName(provider: ModelProvider): string {
  if (provider === "openai") return "OpenAI";
  if (provider === "ollama") return "Ollama (local)";
  if (provider === "openai_compatible") return "OpenAI-compatible endpoint";
  return "Invalid provider selection";
}
