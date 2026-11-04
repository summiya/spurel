import type { EvaluationRunSummary } from "@/lib/evaluation-types";

export interface QualityInterpretation {
  interval: string;
  sample: string;
  coverage: string;
  disclaimer: string;
}

/** Reporting is based solely on saved run metadata, never an estimated metric. */
export function qualityInterpretation(
  run: EvaluationRunSummary | null | undefined,
): QualityInterpretation {
  if (!run) {
    return {
      interval: "N/A",
      sample: "No benchmark selected.",
      coverage: "No judgment coverage measured.",
      disclaimer: "Run an explicit benchmark on labeled cases to see uncertainty.",
    };
  }
  const lower = run.hit_rate_wilson_95_lower;
  const upper = run.hit_rate_wilson_95_upper;
  const interval =
    lower != null &&
    upper != null &&
    Number.isFinite(lower) &&
    Number.isFinite(upper) &&
    lower >= 0 &&
    upper <= 1 &&
    lower <= upper
      ? `${(lower * 100).toFixed(1)}%–${(upper * 100).toFixed(1)}%`
      : "Not measured (older run)";
  const coverage =
    run.mean_judgment_coverage_at_k == null
      ? "Retrieved-result judgment coverage unavailable."
      : `Mean judged-result coverage: ${(run.mean_judgment_coverage_at_k * 100).toFixed(1)}% across ${run.judgment_coverage_case_count}/${run.case_count} cases.`;

  return {
    interval,
    sample:
      run.case_count < 20
        ? `Small labeled sample (${run.case_count} ${run.case_count === 1 ? "case" : "cases"}); estimate is highly uncertain.`
        : `Evaluated ${run.case_count} labeled cases.`,
    coverage,
    disclaimer:
      "Wilson 95% interval describes the observed Hit@K fraction assuming independent sampled cases. Curated or incomplete judgments do not support population-level accuracy claims. This is not model confidence or probability calibration.",
  };
}
