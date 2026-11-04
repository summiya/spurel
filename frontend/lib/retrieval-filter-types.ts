/** All metadata filters are over existing document fields, not arbitrary JSON keys. */
export type DocumentMediaType = "application/pdf" | "text/plain" | "text/markdown";

export interface RetrievalMetadataFilters {
  document_ids?: string[];
  media_types?: DocumentMediaType[];
  filename_contains?: string;
  created_after?: string;
  created_before?: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const MEDIA_TYPES: DocumentMediaType[] = [
  "application/pdf",
  "text/plain",
  "text/markdown",
];
const ALLOWED = [
  "document_ids",
  "media_types",
  "filename_contains",
  "created_after",
  "created_before",
];

/** No unknown fields, regex/pattern operators, arbitrary SQL or unsafe dates. */
export function parseRetrievalMetadataFilters(value: unknown): RetrievalMetadataFilters | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  if (Object.keys(source).some((key) => !ALLOWED.includes(key))) return null;

  const result: RetrievalMetadataFilters = {};
  if ("document_ids" in source) {
    if (
      !Array.isArray(source.document_ids) ||
      source.document_ids.length > 20 ||
      !source.document_ids.every((id: unknown) => typeof id === "string" && UUID.test(id)) ||
      new Set(source.document_ids.map((id: string) => id.toLowerCase())).size !== source.document_ids.length
    )
      return null;
    if (source.document_ids.length) {
      result.document_ids = source.document_ids.map((id: string) => id.toLowerCase());
    }
  }
  if ("media_types" in source) {
    if (
      !Array.isArray(source.media_types) ||
      source.media_types.length > 3 ||
      !source.media_types.every((type: unknown) => MEDIA_TYPES.includes(type as DocumentMediaType)) ||
      new Set(source.media_types).size !== source.media_types.length
    )
      return null;
    if (source.media_types.length) result.media_types = source.media_types;
  }
  if ("filename_contains" in source && source.filename_contains !== null) {
    if (
      typeof source.filename_contains !== "string" ||
      source.filename_contains.trim().length < 1 ||
      source.filename_contains.trim().length > 100 ||
      /[\x00-\x1f\x7f]/.test(source.filename_contains)
    )
      return null;
    result.filename_contains = source.filename_contains.trim();
  }

  for (const name of ["created_after", "created_before"] as const) {
    if (name in source && source[name] !== null) {
      const date = source[name];
      if (
        typeof date !== "string" ||
        !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/.test(date)
      ) return null;
      const stamp = Date.parse(date);
      if (!Number.isFinite(stamp)) return null;
      result[name] = new Date(stamp).toISOString();
    }
  }
  if (
    result.created_after &&
    result.created_before &&
    Date.parse(result.created_after) > Date.parse(result.created_before)
  ) return null;
  return Object.keys(result).length ? result : null;
}

export function retrievalFiltersKey(filters: RetrievalMetadataFilters | null | undefined): string {
  if (!filters) return "";
  return JSON.stringify({
    document_ids: [...(filters.document_ids ?? [])].sort(),
    media_types: [...(filters.media_types ?? [])].sort(),
    filename_contains: filters.filename_contains ?? "",
    created_after: filters.created_after ? new Date(filters.created_after).toISOString() : "",
    created_before: filters.created_before ? new Date(filters.created_before).toISOString() : "",
  });
}

export function describeRetrievalFilters(
  filters: RetrievalMetadataFilters | null | undefined,
): string {
  if (!filters) return "All active documents in this knowledge base";
  const segments: string[] = [];
  if (filters.document_ids?.length) segments.push(`${filters.document_ids.length} document(s)`);
  if (filters.media_types?.length) segments.push(filters.media_types.join(", "));
  if (filters.filename_contains) segments.push(`Filename contains "${filters.filename_contains}"`);
  if (filters.created_after) segments.push(`Uploaded after ${filters.created_after.slice(0, 10)}`);
  if (filters.created_before) segments.push(`Uploaded before ${filters.created_before.slice(0, 10)}`);
  return segments.join(" · ");
}
