import { describe, expect, it } from "vitest";

import {
  isRagAnswerResponse,
  knownAnswerCitationLabels,
  parseRagAnswerRequest,
  type RagSource,
} from "./rag-types";

const trace = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const doc = "d73b06d7-a20e-4ddf-9859-242d69d4372f";
const chunk = "3f7358dd-47f8-4dda-8284-3797e9045b8a";
const source: RagSource = {
  label: "S1",
  retrieval_rank: 1,
  chunk_id: chunk,
  document_id: doc,
  chunk_index: 0,
  excerpt: "Stored evidence from the active index.",
  start_offset: 0,
  end_offset: 38,
  page_start: 1,
  page_end: 1,
  ocr_used: false,
};
const valid = {
  trace_id: trace,
  answer: "The document supports this answer [S1].",
  retrieved_chunk_count: 1,
  generation_provider: "openai",
  generation_model: "example-model",
  sources: [source],
};

describe("SP-15 RAG API contracts", () => {
  it("accepts supported query/configuration with no proxy escapes", () => {
    expect(
      parseRagAnswerRequest({
        query: "  Employee policy  ",
        top_k: 8,
        candidate_k: 50,
        rrf_k: 60,
      }),
    ).toEqual({
      query: "Employee policy",
      top_k: 8,
      candidate_k: 50,
      rrf_k: 60,
    });
  });

  it("rejects malformed and dangerous RAG request settings before paid calls", () => {
    const validRequest = { query: "policy", top_k: 8, candidate_k: 50, rrf_k: 60 };
    const invalid: unknown[] = [
      null,
      [],
      {},
      { ...validRequest, query: " " },
      { ...validRequest, query: "x".repeat(8_001) },
      { ...validRequest, top_k: 0 },
      { ...validRequest, top_k: 21 },
      { ...validRequest, top_k: true },
      { ...validRequest, top_k: 3.14 },
      { ...validRequest, candidate_k: 3 },
      { ...validRequest, candidate_k: 101 },
      { ...validRequest, rrf_k: 0 },
      { ...validRequest, rrf_k: 1001 },
      { ...validRequest, target_url: "http://external.example" },
      { ...validRequest, verify_citations: "yes" },
      { ...validRequest, verify_citations: 1 },
    ];
    for (const value of invalid) expect(parseRagAnswerRequest(value)).toBeNull();
  });

  it("only accepts a strict, opt-in citation review flag", () => {
    const request = { query: "policy", top_k: 8, candidate_k: 50, rrf_k: 60 };
    expect(parseRagAnswerRequest({ ...request, verify_citations: true })).toEqual({
      ...request,
      verify_citations: true,
    });
    expect(parseRagAnswerRequest({ ...request, verify_citations: false })).toEqual(request);
  });

  it("accepts actual grounded answer sources and strict no-context fallback", () => {
    expect(isRagAnswerResponse(valid)).toBe(true);
    expect(
      isRagAnswerResponse({
        trace_id: trace,
        answer: "No usable knowledge-base context was found.",
        retrieved_chunk_count: 0,
        generation_provider: null,
        generation_model: null,
        sources: [],
      }),
    ).toBe(true);
  });

  it("rejects invented, duplicated, or inconsistent source evidence", () => {
    const wrong: unknown[] = [
      { ...valid, trace_id: "fake" },
      { ...valid, retrieved_chunk_count: 0 },
      { ...valid, sources: [{ ...source, label: "S99" }] },
      { ...valid, sources: [{ ...source, chunk_id: "fake" }] },
      { ...valid, sources: [{ ...source, end_offset: -1 }] },
      { ...valid, sources: [source, source], retrieved_chunk_count: 2 },
      { ...valid, sources: [{ ...source, excerpt: "" }] },
      { ...valid, sources: [{ ...source, page_start: 0 }] },
      { ...valid, sources: [{ ...source, page_end: 0 }] },
      { ...valid, sources: [{ ...source, page_start: null, page_end: null, ocr_used: true }] },
      { ...valid, generation_model: 123 },
    ];
    for (const value of wrong) expect(isRagAnswerResponse(value)).toBe(false);
  });

  it("accepts bounded model judgment and rejects invented review outcomes", () => {
    const review = {
      status: "completed",
      verifier_model: "review-model",
      omitted_claim_count: 0,
      claims: [
        {
          id: 1,
          text: "Employees receive 30 days of leave .",
          cited_labels: ["S1"],
          status: "model_supported",
          reason: "The excerpt states this directly.",
        },
        {
          id: 2,
          text: "This claim has no known source.",
          cited_labels: ["S99"],
          status: "invalid_citation",
          reason: "Unknown label.",
        },
      ],
    };
    expect(isRagAnswerResponse({ ...valid, verification: review })).toBe(true);
    expect(
      isRagAnswerResponse({
        ...valid,
        verification: { ...review, claims: [{ ...review.claims[0], status: "proved_true" }] },
      }),
    ).toBe(false);
    expect(
      isRagAnswerResponse({
        ...valid,
        verification: { ...review, claims: [{ ...review.claims[0], cited_labels: ["S99"] }] },
      }),
    ).toBe(false);
    expect(
      isRagAnswerResponse({
        ...valid,
        verification: { ...review, claims: [{ ...review.claims[0], reason: 404 }] },
      }),
    ).toBe(false);
  });

  it("makes only backend-provided source labels navigable", () => {
    expect(knownAnswerCitationLabels("Evidence [S1] but unknown [S2] and [S1].", [source])).toEqual(
      ["S1", "S1"],
    );
  });
});
