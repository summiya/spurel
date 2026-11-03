/** Contracts for the existing Spurel FastAPI evaluation endpoints. */
export type EvaluationMode = "keyword" | "vector" | "hybrid";

export interface EvaluationDataset {
  id: string;
  knowledge_base_id: string;
  name: string;
  case_count: number;
  created_at: string;
}
export interface EvaluationJudgment {
  chunk_id: string;
  relevance: number;
}
export interface EvaluationCaseSummary {
  id: string;
  dataset_id: string;
  query: string;
  judgment_count: number;
  relevant_judgment_count: number;
  created_at: string;
}
export interface EvaluationCase extends Omit<
  EvaluationCaseSummary,
  "judgment_count" | "relevant_judgment_count"
> {
  judgments: EvaluationJudgment[];
}
export interface JudgmentIssue {
  case_id: string;
  chunk_id: string;
  reason: string;
  document_id: string | null;
  chunk_version: number | null;
  active_chunk_version: number | null;
}
export interface JudgmentAudit {
  dataset_id: string;
  case_count: number;
  judgment_count: number;
  is_usable: boolean;
  invalid_count: number;
  inactive_version_count: number;
  missing_or_out_of_scope_count: number;
  issues_truncated: boolean;
  issues: JudgmentIssue[];
}
export interface EvaluationMetrics {
  mode: EvaluationMode;
  top_k: number;
  candidate_k: number | null;
  rrf_k: number | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  case_count: number;
  mean_duration_ms: number;
  total_duration_ms: number;
  judgment_coverage_case_count: number;
  mean_judgment_coverage_at_k: number | null;
  mean_precision_at_k: number;
  mean_recall_at_k: number;
  mrr_at_k: number;
  mean_ndcg_at_k: number;
  created_at: string;
}
export interface EvaluationRunSummary extends EvaluationMetrics {
  run_id: string;
  dataset_id: string;
}
export interface EvaluationCaseMetric {
  position: number;
  case_id: string;
  query: string;
  duration_ms: number;
  judged_count: number;
  relevant_count: number;
  retrieved_count_at_k: number;
  judged_retrieved_at_k: number;
  relevant_retrieved_at_k: number;
  judgment_coverage_at_k: number | null;
  precision_at_k: number;
  recall_at_k: number;
  reciprocal_rank_at_k: number;
  ndcg_at_k: number;
}
export interface EvaluationRun extends EvaluationRunSummary {
  knowledge_base_id: string;
  cases: EvaluationCaseMetric[];
}
export interface EvaluationComparison {
  dataset_id: string;
  first: EvaluationRunSummary;
  second: EvaluationRunSummary;
  same_retrieval_configuration: boolean;
  same_case_set: boolean;
  aggregate_comparable: boolean;
  shared_case_count: number;
  first_only_case_count: number;
  second_only_case_count: number;
  comparable_case_count: number;
  query_changed_case_count: number;
  total_duration_delta_ms: number | null;
  mean_duration_delta_ms: number | null;
  mean_judgment_coverage_delta: number | null;
  mean_precision_delta: number | null;
  mean_recall_delta: number | null;
  mrr_delta: number | null;
  mean_ndcg_delta: number | null;
  cases: Array<{
    case_id: string;
    presence: string;
    first_query: string | null;
    second_query: string | null;
    query_changed: boolean;
    comparable: boolean;
    precision_delta: number | null;
    recall_delta: number | null;
    reciprocal_rank_delta: number | null;
    ndcg_delta: number | null;
    duration_delta_ms: number | null;
  }>;
}
export interface EvaluationBaseline {
  baseline_id: string;
  dataset_id: string;
  run_id: string;
  mode: EvaluationMode;
  top_k: number;
  promoted_at: string;
  configuration_fingerprint: string;
}
export interface QualityGate {
  status: "pass" | "fail" | "not_evaluable";
  aggregate_comparable: boolean;
  same_retrieval_configuration: boolean;
  unavailable_metrics: string[];
  checks: Array<{
    metric: string;
    first_value: number;
    second_value: number;
    delta: number;
    allowed_regression: number;
    regression_amount: number;
    passed: boolean;
  }>;
}

export function percent(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "N/A"
    : (value * 100).toFixed(1) + "%";
}
export function deltaPercent(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "N/A"
    : (value >= 0 ? "+" : "") + (value * 100).toFixed(1) + " pp";
}
export function isEvaluationMode(value: unknown): value is EvaluationMode {
  return value === "keyword" || value === "vector" || value === "hybrid";
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function isUUID(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value);
}
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function keys(value: Record<string, unknown>, allowed: string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}
function integer(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max;
}
function number(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
function pair(value: Record<string, unknown>): boolean {
  return (
    isUUID(value.first_run_id) &&
    isUUID(value.second_run_id) &&
    value.first_run_id !== value.second_run_id
  );
}

/** Strict allowlist before any browser mutation reaches FastAPI. */
export function parseEvaluationPayload(
  kind: string,
  input: unknown,
): Record<string, unknown> | null {
  if (!object(input)) return null;
  if (kind === "dataset") {
    if (!keys(input, ["name"]) || typeof input.name !== "string") return null;
    const name = input.name.trim();
    return name.length >= 1 && name.length <= 120 ? { name } : null;
  }
  if (kind === "case") {
    if (
      !keys(input, ["query", "judgments"]) ||
      typeof input.query !== "string" ||
      !Array.isArray(input.judgments)
    )
      return null;
    const query = input.query.trim();
    if (!query || query.length > 8000 || !integer(input.judgments.length, 1, 100)) return null;
    const seen = new Set<string>();
    let relevant = 0;
    for (const item of input.judgments) {
      if (
        !object(item) ||
        !keys(item, ["chunk_id", "relevance"]) ||
        !isUUID(item.chunk_id) ||
        !integer(item.relevance, 0, 3) ||
        seen.has(item.chunk_id.toLowerCase())
      )
        return null;
      seen.add(item.chunk_id.toLowerCase());
      if (item.relevance > 0) relevant += 1;
    }
    return relevant ? { query, judgments: input.judgments } : null;
  }
  if (kind === "keyword" || kind === "vector" || kind === "hybrid") {
    const allowed = kind === "hybrid" ? ["top_k", "candidate_k", "rrf_k"] : ["top_k"];
    if (!keys(input, allowed) || !integer(input.top_k, 1, 100)) return null;
    if (kind === "hybrid") {
      if (!integer(input.candidate_k, input.top_k, 100) || !integer(input.rrf_k, 1, 1000))
        return null;
      return { top_k: input.top_k, candidate_k: input.candidate_k, rrf_k: input.rrf_k };
    }
    return { top_k: input.top_k };
  }
  if (kind === "compare") {
    return keys(input, ["first_run_id", "second_run_id"]) && pair(input)
      ? { first_run_id: input.first_run_id, second_run_id: input.second_run_id }
      : null;
  }
  if (kind === "gate") {
    if (
      !keys(input, ["first_run_id", "second_run_id", "thresholds"]) ||
      !pair(input) ||
      !object(input.thresholds)
    )
      return null;
    const allowed = [
      "max_mean_precision_drop",
      "max_mean_recall_drop",
      "max_mrr_drop",
      "max_mean_ndcg_drop",
      "max_mean_judgment_coverage_drop",
      "max_mean_duration_increase_ms",
    ];
    if (!keys(input.thresholds, allowed) || Object.keys(input.thresholds).length === 0) return null;
    for (const [key, value] of Object.entries(input.thresholds)) {
      if (!number(value, 0, key === "max_mean_duration_increase_ms" ? 1_000_000_000 : 1))
        return null;
    }
    return input;
  }
  if (kind === "promote") {
    return keys(input, ["run_id"]) && isUUID(input.run_id) ? { run_id: input.run_id } : null;
  }
  return null;
}
