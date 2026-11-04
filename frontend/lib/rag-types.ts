/** Exact request and response contracts for the existing FastAPI RAG answer endpoint. */
export interface RagAnswerRequest {
  query: string;
  top_k: number;
  candidate_k: number;
  rrf_k: number;
}

export interface RagSource {
  label: string;
  retrieval_rank: number;
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  excerpt: string;
  start_offset: number;
  end_offset: number;
  page_start?: number | null;
  page_end?: number | null;
  ocr_used?: boolean;
}

export interface RagAnswerResponse {
  trace_id: string;
  answer: string;
  retrieved_chunk_count: number;
  generation_provider: string | null;
  generation_model: string | null;
  sources: RagSource[];
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function integer(value: unknown, minimum: number, maximum: number): value is number {
  return (
    typeof value === "number" && Number.isInteger(value) && value >= minimum && value <= maximum
  );
}

function uuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

/** Rejects unknown fields and backend-unsupported settings before provider calls. */
export function parseRagAnswerRequest(value: unknown): RagAnswerRequest | null {
  if (!record(value)) return null;
  if (
    Object.keys(value).some((key) => !["query", "top_k", "candidate_k", "rrf_k"].includes(key)) ||
    typeof value.query !== "string"
  )
    return null;

  const query = value.query.trim();
  if (
    query.length < 1 ||
    query.length > 8_000 ||
    !integer(value.top_k, 1, 20) ||
    !integer(value.candidate_k, value.top_k, 100) ||
    !integer(value.rrf_k, 1, 1_000)
  )
    return null;

  return {
    query,
    top_k: value.top_k,
    candidate_k: value.candidate_k,
    rrf_k: value.rrf_k,
  };
}

/** Refuse inconsistent backend evidence rather than presenting synthetic citations. */
export function isRagAnswerResponse(value: unknown): value is RagAnswerResponse {
  if (!record(value)) return false;
  if (
    !uuid(value.trace_id) ||
    typeof value.answer !== "string" ||
    value.answer.length > 500_000 ||
    !integer(value.retrieved_chunk_count, 0, 20) ||
    !(value.generation_provider === null || typeof value.generation_provider === "string") ||
    !(value.generation_model === null || typeof value.generation_model === "string") ||
    !Array.isArray(value.sources) ||
    value.sources.length > value.retrieved_chunk_count
  )
    return false;

  const labels = new Set<string>();
  const ranks = new Set<number>();
  const chunkIds = new Set<string>();
  for (const item of value.sources) {
    if (!record(item)) return false;
    if (
      typeof item.label !== "string" ||
      !/^S(?:[1-9]|1[0-9]|20)$/.test(item.label) ||
      !integer(item.retrieval_rank, 1, 20) ||
      !uuid(item.chunk_id) ||
      !uuid(item.document_id) ||
      !integer(item.chunk_index, 0, 10_000_000) ||
      typeof item.excerpt !== "string" ||
      item.excerpt.length === 0 ||
      !integer(item.start_offset, 0, Number.MAX_SAFE_INTEGER) ||
      !integer(item.end_offset, item.start_offset, Number.MAX_SAFE_INTEGER) ||
      !(
        (item.page_start == null && item.page_end == null && item.ocr_used !== true) ||
        (integer(item.page_start, 1, 500) &&
          integer(item.page_end, item.page_start, 500) &&
          (item.ocr_used === undefined || typeof item.ocr_used === "boolean"))
      ) ||
      labels.has(item.label) ||
      ranks.has(item.retrieval_rank) ||
      chunkIds.has(item.chunk_id.toLowerCase())
    )
      return false;
    labels.add(item.label);
    ranks.add(item.retrieval_rank);
    chunkIds.add(item.chunk_id.toLowerCase());
  }

  if (value.retrieved_chunk_count === 0) {
    return (
      value.sources.length === 0 &&
      value.generation_provider === null &&
      value.generation_model === null
    );
  }
  return value.sources.length > 0;
}

/** Only evidence labels actually supplied by the API become clickable. */
export function knownAnswerCitationLabels(answer: string, sources: RagSource[]): string[] {
  const known = new Set(sources.map((source) => source.label));
  return (answer.match(/\[S\d+\]/g) ?? [])
    .map((token) => token.slice(1, -1))
    .filter((label) => known.has(label));
}
