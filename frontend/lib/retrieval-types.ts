export type RetrievalMode = "vector" | "keyword" | "hybrid";

export interface RetrievalParameters {
  query: string;
  top_k: number;
  candidate_k?: number;
  rrf_k?: number;
}

export interface RetrievalMatch {
  rank: number;
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  start_offset: number;
  end_offset: number;
  cosine_similarity?: number | null;
  keyword_score?: number | null;
  rrf_score?: number | null;
  vector_rank?: number | null;
  keyword_rank?: number | null;
}

export interface RetrievalResult extends RetrievalParameters {
  mode: RetrievalMode;
  trace_id: string;
  duration_ms: number;
  matches: RetrievalMatch[];
}

export interface RetrievalTraceDetail {
  id: string;
  knowledge_base_id: string;
  mode: RetrievalMode;
  query: string;
  top_k: number;
  candidate_k: number | null;
  rrf_k: number | null;
  duration_ms: number;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  created_at: string;
  results: RetrievalMatch[];
}

const MODES: ReadonlyArray<RetrievalMode> = ["vector", "keyword", "hybrid"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function boundedInteger(value: unknown, minimum: number, maximum: number): value is number {
  return (
    typeof value === "number" && Number.isInteger(value) && value >= minimum && value <= maximum
  );
}

export function isRetrievalMode(value: string): value is RetrievalMode {
  return MODES.some((mode) => mode === value);
}

export function parseRetrievalRequest(
  mode: RetrievalMode,
  value: unknown,
): RetrievalParameters | null {
  if (!isRecord(value)) return null;
  const required =
    mode === "hybrid" ? ["query", "top_k", "candidate_k", "rrf_k"] : ["query", "top_k"];
  if (Object.keys(value).some((key) => !required.includes(key))) return null;
  if (typeof value.query !== "string") return null;
  const query = value.query.trim();
  if (query.length < 1 || query.length > 8_000) return null;
  if (!boundedInteger(value.top_k, 1, 100)) return null;

  if (mode !== "hybrid") {
    return { query, top_k: value.top_k };
  }
  if (
    !boundedInteger(value.candidate_k, value.top_k, 100) ||
    !boundedInteger(value.rrf_k, 1, 1_000)
  )
    return null;

  return {
    query,
    top_k: value.top_k,
    candidate_k: value.candidate_k,
    rrf_k: value.rrf_k,
  };
}

export function isRetrievalResult(value: unknown): value is RetrievalResult {
  if (!isRecord(value) || !isRetrievalMode(String(value.mode))) return false;
  if (
    typeof value.trace_id !== "string" ||
    typeof value.query !== "string" ||
    !boundedInteger(value.top_k, 1, 100) ||
    typeof value.duration_ms !== "number" ||
    !Number.isFinite(value.duration_ms) ||
    value.duration_ms < 0 ||
    !Array.isArray(value.matches) ||
    value.matches.length > value.top_k
  )
    return false;
  if (
    value.mode === "hybrid" &&
    (!boundedInteger(value.candidate_k, value.top_k, 100) || !boundedInteger(value.rrf_k, 1, 1_000))
  )
    return false;

  return value.matches.every((item: unknown, index: number) => {
    if (!isRecord(item)) return false;
    if (
      item.rank !== index + 1 ||
      typeof item.chunk_id !== "string" ||
      typeof item.document_id !== "string" ||
      typeof item.text !== "string" ||
      !boundedInteger(item.chunk_index, 0, 10_000_000) ||
      typeof item.start_offset !== "number" ||
      typeof item.end_offset !== "number"
    )
      return false;
    const primary =
      value.mode === "vector"
        ? item.cosine_similarity
        : value.mode === "keyword"
          ? item.keyword_score
          : item.rrf_score;
    return typeof primary === "number" && Number.isFinite(primary);
  });
}

export function mainScore(
  match: RetrievalMatch,
  mode: RetrievalMode,
): {
  label: string;
  value: string;
} {
  if (mode === "vector")
    return {
      label: "Cosine similarity",
      value:
        match.cosine_similarity === null || match.cosine_similarity === undefined
          ? "—"
          : match.cosine_similarity.toFixed(4),
    };
  if (mode === "keyword")
    return {
      label: "PostgreSQL FTS",
      value:
        match.keyword_score === null || match.keyword_score === undefined
          ? "—"
          : match.keyword_score.toFixed(5),
    };
  return {
    label: "RRF score",
    value:
      match.rrf_score === null || match.rrf_score === undefined ? "—" : match.rrf_score.toFixed(6),
  };
}

export function otherScore(score: number | null | undefined, decimals: number): string {
  return score === null || score === undefined ? "Not present" : score.toFixed(decimals);
}
