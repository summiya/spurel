import { describe, expect, it } from "vitest";

import { qualityInterpretation } from "./quality-uncertainty";
import type { EvaluationRunSummary } from "./evaluation-types";

const run = {
  run_id: "a",
  case_count: 5,
  mean_judgment_coverage_at_k: 0.4,
  judgment_coverage_case_count: 4,
  hit_rate_at_k: 0.6,
  hit_rate_wilson_95_lower: 0.23,
  hit_rate_wilson_95_upper: 0.88,
} as EvaluationRunSummary;

describe("SP-24 sample-aware report", () => {
  it("shows only measured intervals and warns about small curated samples", () => {
    const result = qualityInterpretation(run);
    expect(result.interval).toBe("23.0%–88.0%");
    expect(result.sample).toContain("Small labeled sample");
    expect(result.coverage).toContain("40.0%");
    expect(result.disclaimer).toContain("not model confidence");
  });

  it("does not fabricate historical intervals", () => {
    expect(qualityInterpretation({ ...run, hit_rate_wilson_95_lower: null }).interval).toBe(
      "Not measured (older run)",
    );
    expect(qualityInterpretation(null).interval).toBe("N/A");
  });

  it("rejects impossible intervals and supports sufficiently sized runs", () => {
    expect(
      qualityInterpretation({
        ...run,
        case_count: 40,
        hit_rate_wilson_95_lower: 0.9,
        hit_rate_wilson_95_upper: 0.1,
      }).interval,
    ).toBe("Not measured (older run)");
    expect(qualityInterpretation({ ...run, case_count: 40 }).sample).toContain("40 labeled cases");
  });
});
