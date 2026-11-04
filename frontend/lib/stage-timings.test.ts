import { describe, expect, it } from "vitest";

import { displayStageTime, isStageTimings } from "./stage-timings";

describe("real stage timing contracts", () => {
  it("accepts measured nonnegative stage durations, including zero", () => {
    expect(isStageTimings({ query_embedding: 12.5, vector_search: 0 })).toBe(true);
    expect(displayStageTime(0.125)).toBe("0.125 ms");
    expect(displayStageTime(12.5)).toBe("12.5 ms");
    expect(displayStageTime(null)).toBe("Not recorded");
  });

  it("rejects fabricated or invalid stage data", () => {
    for (const value of [
      {},
      null,
      [],
      { fake_stage: 1 },
      { vector_search: Number.NaN },
      { vector_search: Number.POSITIVE_INFINITY },
      { keyword_search: -1 },
      { rrf_fusion: "0" },
      { query_embedding: true },
    ]) {
      expect(isStageTimings(value)).toBe(false);
    }
  });
});
