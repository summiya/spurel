/** Bounded, measured retrieval stage names; no inferred timings. */
export const RETRIEVAL_STAGES = [
  { key: "query_embedding", label: "Query embedding" },
  { key: "vector_search", label: "Vector search" },
  { key: "keyword_search", label: "Keyword search" },
  { key: "rrf_fusion", label: "RRF fusion" },
  { key: "cross_encoder", label: "Cross-encoder scoring" },
] as const;

export type RetrievalStage = (typeof RETRIEVAL_STAGES)[number]["key"];
export type StageTimings = Partial<Record<RetrievalStage, number>>;

export function isStageTimings(value: unknown): value is StageTimings {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const pairs = Object.entries(value);
  return (
    pairs.length > 0 &&
    pairs.length <= RETRIEVAL_STAGES.length &&
    pairs.every(
      ([key, elapsed]) =>
        RETRIEVAL_STAGES.some((stage) => stage.key === key) &&
        typeof elapsed === "number" &&
        Number.isFinite(elapsed) &&
        elapsed >= 0,
    )
  );
}

export function displayStageTime(elapsed: number | null | undefined): string {
  if (elapsed == null) return "Not recorded";
  return `${elapsed < 1 ? elapsed.toFixed(3) : elapsed.toFixed(1)} ms`;
}
