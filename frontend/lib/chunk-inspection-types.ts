export interface ChunkVersion {
  version: number;
  chunk_count: number;
  created_at: string;
  is_active: boolean;
  status: "processing" | "ready" | "failed";
  attempt_count: number;
}

export interface PersistedChunk {
  id: string;
  document_id: string;
  index: number;
  text: string;
  start_offset: number;
  end_offset: number;
  has_embeddings: boolean;
  embedding_count: number;
  token_count?: number | null;
  tokenizer_encoding?: string | null;
}

export interface InspectedChunksPage {
  items: PersistedChunk[];
  limit: number;
  offset: number;
  version?: number;
}

export function parseChunkVersion(value: string | null): number | null | undefined {
  if (value === null) return null;
  if (!/^[1-9][0-9]{0,5}$/.test(value)) return undefined;
  const version = Number(value);
  return Number.isSafeInteger(version) ? version : undefined;
}
