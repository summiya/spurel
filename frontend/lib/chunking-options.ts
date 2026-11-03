/** Exact SP-16 document processing options; legacy no-body POST remains valid. */
export type ChunkStrategy = "characters" | "tokens" | "recursive" | "markdown" | "sentences";

export interface ChunkingOptions {
  strategy: ChunkStrategy;
  chunk_size: number;
  overlap: number;
}

export const DEFAULT_CHUNKING: ChunkingOptions = {
  strategy: "characters",
  chunk_size: 1000,
  overlap: 200,
};

export const TOKEN_CHUNKING: ChunkingOptions = {
  strategy: "tokens",
  chunk_size: 512,
  overlap: 64,
};

/** All structured strategies use character bounds and retain the existing safe defaults. */
export const STRUCTURED_CHUNKING: ChunkingOptions = {
  strategy: "recursive",
  chunk_size: 1000,
  overlap: 200,
};

export function parseChunkingOptions(value: unknown): ChunkingOptions | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).length !== 3 ||
    !Object.keys(record).every((key) => ["strategy", "chunk_size", "overlap"].includes(key))
  )
    return null;
  if (
    record.strategy !== "characters" &&
    record.strategy !== "tokens" &&
    record.strategy !== "recursive" &&
    record.strategy !== "markdown" &&
    record.strategy !== "sentences"
  )
    return null;
  const max = record.strategy === "tokens" ? 2000 : 20000;
  if (
    typeof record.chunk_size !== "number" ||
    !Number.isInteger(record.chunk_size) ||
    record.chunk_size < 1 ||
    record.chunk_size > max ||
    typeof record.overlap !== "number" ||
    !Number.isInteger(record.overlap) ||
    record.overlap < 0 ||
    record.overlap >= record.chunk_size
  )
    return null;
  return {
    strategy: record.strategy,
    chunk_size: record.chunk_size,
    overlap: record.overlap,
  };
}

export function isLegacyChunking(value: ChunkingOptions): boolean {
  return (
    value.strategy === "characters" &&
    value.chunk_size === DEFAULT_CHUNKING.chunk_size &&
    value.overlap === DEFAULT_CHUNKING.overlap
  );
}
