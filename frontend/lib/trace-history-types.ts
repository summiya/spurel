import type { RetrievalMode, RetrievalTraceDetail } from "@/lib/retrieval-types";
import type { RetrievalMetadataFilters } from "@/lib/retrieval-filter-types";
import type { StageTimings } from "@/lib/stage-timings";

export interface RetrievalTraceSummary {
  id: string;
  mode: RetrievalMode;
  query: string;
  top_k: number;
  candidate_k: number | null;
  rrf_k: number | null;
  duration_ms: number;
  stage_timings_ms?: StageTimings | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  result_count: number;
  reranker_model?: string | null;
  created_at: string;
  filters?: RetrievalMetadataFilters | null;
}

export type TraceComparisonSide = Omit<
  RetrievalTraceDetail,
  "id" | "knowledge_base_id" | "created_at" | "results"
> & { trace_id: string; result_count: number };

export interface TraceComparisonResult {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  start_offset: number;
  end_offset: number;
  first_rank: number | null;
  second_rank: number | null;
  rank_delta: number | null;
  first_cosine_similarity: number | null;
  second_cosine_similarity: number | null;
  first_keyword_score: number | null;
  second_keyword_score: number | null;
  first_rrf_score: number | null;
  second_rrf_score: number | null;
  first_candidate_rank?: number | null;
  second_candidate_rank?: number | null;
  first_rerank_score?: number | null;
  second_rerank_score?: number | null;
}

export interface TraceComparison {
  first: TraceComparisonSide;
  second: TraceComparisonSide;
  same_query: boolean;
  overlap_count: number;
  union_count: number;
  overlap_ratio: number | null;
  first_only_count: number;
  second_only_count: number;
  duration_delta_ms: number;
  results: TraceComparisonResult[];
}

export interface TraceComparisonRequest {
  first_trace_id: string;
  second_trace_id: string;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseTraceComparisonRequest(value: unknown): TraceComparisonRequest | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).length !== 2 ||
    typeof record.first_trace_id !== "string" ||
    typeof record.second_trace_id !== "string" ||
    !UUID_PATTERN.test(record.first_trace_id) ||
    !UUID_PATTERN.test(record.second_trace_id) ||
    record.first_trace_id.toLowerCase() === record.second_trace_id.toLowerCase()
  )
    return null;

  return { first_trace_id: record.first_trace_id, second_trace_id: record.second_trace_id };
}

export function rankMovement(
  delta: number | null,
  firstRank: number | null,
  secondRank: number | null,
): string {
  if (firstRank === null) return "Only in B";
  if (secondRank === null) return "Only in A";
  if (delta === null) return "Unknown";
  if (delta < 0) return `Up ${Math.abs(delta)}`;
  if (delta > 0) return `Down ${delta}`;
  return "Unchanged";
}

export function formatTraceScore(score: number | null, decimals: number): string {
  return score === null ? "—" : score.toFixed(decimals);
}

export function traceScoreLabel(mode: RetrievalMode): string {
  return mode === "vector" ? "Cosine" : mode === "keyword" ? "Postgres FTS" : "RRF";
}
