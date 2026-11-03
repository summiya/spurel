import { describe, expect, it } from "vitest";

import {
  isRetrievalMode,
  isRetrievalResult,
  mainScore,
  otherScore,
  parseRetrievalRequest,
  type RetrievalMatch,
} from "./retrieval-types";

const chunk: RetrievalMatch = {
  rank: 1,
  chunk_id: "b71a0d37-637d-4f55-9749-40d6d1c2b953",
  document_id: "2aeb68c9-f95d-46db-a9a3-552ce8931913",
  chunk_index: 0,
  text: "A stored excerpt",
  start_offset: 10,
  end_offset: 26,
  page_start: 2,
  page_end: 3,
  ocr_used: true,
  cosine_similarity: 0.91426,
  keyword_score: 0.08942,
  rrf_score: 0.032786,
  vector_rank: 1,
  keyword_rank: 2,
};

describe("retrieval payloads and scores", () => {
  it("accepts only the three implemented retrieval strategies", () => {
    for (const mode of ["vector", "keyword", "hybrid"]) {
      expect(isRetrievalMode(mode)).toBe(true);
    }
    expect(isRetrievalMode("bm25")).toBe(false);
    expect(isRetrievalMode("../rag/answer")).toBe(false);
  });

  it("trims bounded queries and rejects extraneous/invalid fields", () => {
    expect(parseRetrievalRequest("keyword", { query: "  backup  ", top_k: 10 })).toEqual({
      query: "backup",
      top_k: 10,
    });
    expect(parseRetrievalRequest("vector", { query: "search", top_k: 1 })).toEqual({
      query: "search",
      top_k: 1,
    });
    const invalid: unknown[] = [
      null,
      [],
      { query: "", top_k: 10 },
      { query: " ", top_k: 1 },
      { query: "a".repeat(8_001), top_k: 10 },
      { query: "source", top_k: 0 },
      { query: "source", top_k: 101 },
      { query: "source", top_k: 3.14 },
      { query: "source", top_k: true },
      { query: "source", top_k: 10, candidate_k: 50 },
      { query: "source", top_k: 10, redirect: "http://evil.test" },
    ];
    for (const value of invalid) {
      expect(parseRetrievalRequest("keyword", value)).toBeNull();
    }
  });

  it("requires valid hybrid candidate and RRF bounds", () => {
    expect(
      parseRetrievalRequest("hybrid", {
        query: "history",
        top_k: 10,
        candidate_k: 50,
        rrf_k: 60,
      }),
    ).toEqual({ query: "history", top_k: 10, candidate_k: 50, rrf_k: 60 });
    for (const candidate_k of [0, 9, 101]) {
      expect(
        parseRetrievalRequest("hybrid", {
          query: "history",
          top_k: 10,
          candidate_k,
          rrf_k: 60,
        }),
      ).toBeNull();
    }
    for (const rrf_k of [0, 1001, 6.4]) {
      expect(
        parseRetrievalRequest("hybrid", {
          query: "history",
          top_k: 10,
          candidate_k: 50,
          rrf_k,
        }),
      ).toBeNull();
    }
  });

  it("rejects inconsistent or invented PDF page provenance", () => {
    const valid = {
      mode: "vector",
      trace_id: "trace-test",
      duration_ms: 1.5,
      query: "test",
      top_k: 5,
      matches: [chunk],
    };
    expect(isRetrievalResult(valid)).toBe(true);
    expect(
      isRetrievalResult({
        ...valid,
        matches: [{ ...chunk, page_start: 0 }],
      }),
    ).toBe(false);
    expect(
      isRetrievalResult({
        ...valid,
        matches: [{ ...chunk, page_end: 1 }],
      }),
    ).toBe(false);
    expect(
      isRetrievalResult({
        ...valid,
        matches: [{ ...chunk, page_start: null, page_end: null, ocr_used: true }],
      }),
    ).toBe(false);
  });

  it("validates real response shape without fabricating scores", () => {
    const keyword = {
      mode: "keyword",
      query: "query",
      trace_id: "a55cc93b-08f4-4b83-a9ae-5a87ebc5f6ae",
      top_k: 5,
      duration_ms: 13.33,
      matches: [{ ...chunk, keyword_score: 0.00004 }],
    };
    expect(isRetrievalResult(keyword)).toBe(true);
    expect(isRetrievalResult({ ...keyword, matches: [{ ...chunk, rank: 2 }] })).toBe(false);
    expect(isRetrievalResult({ ...keyword, duration_ms: null })).toBe(false);
    expect(isRetrievalResult({ ...keyword, duration_ms: -1 })).toBe(false);
    expect(isRetrievalResult({ ...keyword, matches: [{ ...chunk, keyword_score: null }] })).toBe(
      false,
    );
    expect(isRetrievalResult({ ...keyword, mode: "hybrid", candidate_k: 2, rrf_k: 60 })).toBe(
      false,
    );
  });

  it("reports raw, incomparable backend score scales", () => {
    expect(mainScore(chunk, "vector")).toEqual({
      label: "Cosine similarity",
      value: "0.9143",
    });
    expect(mainScore(chunk, "keyword")).toEqual({
      label: "PostgreSQL FTS",
      value: "0.08942",
    });
    expect(mainScore(chunk, "hybrid")).toEqual({
      label: "RRF score",
      value: "0.032786",
    });
    expect(otherScore(null, 4)).toBe("Not present");
    expect(otherScore(0, 4)).toBe("0.0000");
  });
});
