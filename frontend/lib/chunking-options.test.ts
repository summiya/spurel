import { describe, expect, it } from "vitest";
import {
  DEFAULT_CHUNKING,
  TOKEN_CHUNKING,
  isLegacyChunking,
  parseChunkingOptions,
} from "./chunking-options";

describe("SP-16 explicit document chunking controls", () => {
  it("preserves legacy defaults and validates an explicit token strategy", () => {
    expect(isLegacyChunking(DEFAULT_CHUNKING)).toBe(true);
    expect(parseChunkingOptions(DEFAULT_CHUNKING)).toEqual(DEFAULT_CHUNKING);
    expect(parseChunkingOptions(TOKEN_CHUNKING)).toEqual(TOKEN_CHUNKING);
    expect(isLegacyChunking(TOKEN_CHUNKING)).toBe(false);
    expect(parseChunkingOptions({ strategy: "characters", chunk_size: 20000, overlap: 19999 }))
      .not.toBeNull();
    expect(parseChunkingOptions({ strategy: "tokens", chunk_size: 2000, overlap: 0 }))
      .not.toBeNull();
  });

  it("rejects unknown strategies, malformed bodies, overlap violations and unsafe limits", () => {
    for (const value of [
      null,
      [],
      {},
      { ...TOKEN_CHUNKING, strategy: "auto" },
      { ...TOKEN_CHUNKING, chunk_size: 2001 },
      { ...TOKEN_CHUNKING, overlap: 512 },
      { ...TOKEN_CHUNKING, overlap: -1 },
      { ...TOKEN_CHUNKING, chunk_size: 0 },
      { ...TOKEN_CHUNKING, chunk_size: true },
      { ...TOKEN_CHUNKING, chunk_size: 1.5 },
      { ...TOKEN_CHUNKING, arbitraryUrl: "http://example.com" },
      { strategy: "tokens", chunk_size: 512 },
    ]) {
      expect(parseChunkingOptions(value)).toBeNull();
    }
  });
});
