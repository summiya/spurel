import { describe, expect, it } from "vitest";
import { deltaPercent, parseEvaluationPayload, percent } from "./evaluation-types";

const a = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const b = "d73b06d7-a20e-4ddf-9859-242d69d4372f";

describe("SP-14 evaluation contracts", () => {
  it("normalizes dataset names and rejects unknown fields", () => {
    expect(parseEvaluationPayload("dataset", { name: "  Support Q&A  " })).toEqual({ name: "Support Q&A" });
    expect(parseEvaluationPayload("dataset", { name: " ", admin: true })).toBeNull();
    expect(parseEvaluationPayload("dataset", { name: "x".repeat(121) })).toBeNull();
  });
  it("requires active-chunk-shaped judgments, unique IDs and at least one relevant grade", () => {
    const valid = { query: "Where is the policy?", judgments: [{ chunk_id: a, relevance: 3 }, { chunk_id: b, relevance: 0 }] };
    expect(parseEvaluationPayload("case", valid)).toEqual(valid);
    expect(parseEvaluationPayload("case", { ...valid, judgments: [{ chunk_id: a, relevance: 0 }] })).toBeNull();
    expect(parseEvaluationPayload("case", { ...valid, judgments: [{ chunk_id: a, relevance: 2 }, { chunk_id: a, relevance: 3 }] })).toBeNull();
    expect(parseEvaluationPayload("case", { ...valid, judgments: [{ chunk_id: a, relevance: true }] })).toBeNull();
    expect(parseEvaluationPayload("case", { ...valid, query: "" })).toBeNull();
  });
  it("enforces cost-controlled retrieval bounds and strict comparison pairs", () => {
    expect(parseEvaluationPayload("keyword", { top_k: 10 })).toEqual({ top_k: 10 });
    expect(parseEvaluationPayload("keyword", { top_k: 10, candidate_k: 50 })).toBeNull();
    expect(parseEvaluationPayload("vector", { top_k: 101 })).toBeNull();
    expect(parseEvaluationPayload("hybrid", { top_k: 10, candidate_k: 5, rrf_k: 60 })).toBeNull();
    expect(parseEvaluationPayload("hybrid", { top_k: 10, candidate_k: 50, rrf_k: 60 })).not.toBeNull();
    expect(parseEvaluationPayload("compare", { first_run_id: a, second_run_id: b })).not.toBeNull();
    expect(parseEvaluationPayload("compare", { first_run_id: a, second_run_id: a })).toBeNull();
  });
  it("rejects empty/invalid quality gates, accepts explicit thresholds and protects baseline promotion", () => {
    expect(parseEvaluationPayload("gate", { first_run_id: a, second_run_id: b, thresholds: {} })).toBeNull();
    expect(parseEvaluationPayload("gate", { first_run_id: a, second_run_id: b, thresholds: { max_mean_recall_drop: 2 } })).toBeNull();
    expect(parseEvaluationPayload("gate", { first_run_id: a, second_run_id: b, thresholds: { max_mean_recall_drop: 0.05 } })).not.toBeNull();
    expect(parseEvaluationPayload("promote", { run_id: a })).toEqual({ run_id: a });
    expect(parseEvaluationPayload("promote", { run_id: a, is_admin: true })).toBeNull();
  });
  it("never invents metrics for missing history", () => {
    expect(percent(null)).toBe("N/A");
    expect(deltaPercent(null)).toBe("N/A");
    expect(percent(0.94)).toBe("94.0%");
    expect(deltaPercent(-0.025)).toBe("-2.5 pp");
  });
});
