import { RETRIEVAL_STAGES, displayStageTime, type StageTimings } from "@/lib/stage-timings";

/** Exact reported timings. Neither this view nor comparisons estimate missing values. */
export function StageTimingBreakdown({ timings }: { timings?: StageTimings | null }) {
  const stages = RETRIEVAL_STAGES.filter((item) => timings?.[item.key] !== undefined);
  return (
    <section aria-label="Measured retrieval stage timings">
      <h3 className="subsection-title">Retrieval stages</h3>
      {stages.length ? (
        <div className="retrieval-score-facts">
          {stages.map((stage) => (
            <div key={stage.key}>
              <small>{stage.label}</small>
              <strong>{displayStageTime(timings?.[stage.key])}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-hint">No stage timings were recorded for this run.</p>
      )}
      <p className="text-hint">
        Measured service-stage elapsed time. Hybrid branches run concurrently, so stage times can
        overlap and must not be added together. Total duration excludes saving the trace.
      </p>
    </section>
  );
}

/** Side-by-side observed timings; a delta only exists when both runs measured a stage. */
export function StageTimingComparison({
  first,
  second,
}: {
  first?: StageTimings | null;
  second?: StageTimings | null;
}) {
  const stages = RETRIEVAL_STAGES.filter(
    (stage) => first?.[stage.key] !== undefined || second?.[stage.key] !== undefined,
  );
  return (
    <section aria-label="Per-stage timing comparison">
      <h3 className="subsection-title">Measured stages · A vs B</h3>
      {stages.length ? (
        <div className="trace-detail-facts">
          {stages.map((stage) => {
            const a = first?.[stage.key];
            const b = second?.[stage.key];
            const delta = a == null || b == null ? null : b - a;
            return (
              <span key={stage.key}>
                <strong>{stage.label}</strong> · A {displayStageTime(a)} / B {displayStageTime(b)}
                {delta === null
                  ? " · Δ not available"
                  : ` · B − A ${delta > 0 ? "+" : ""}${displayStageTime(delta)}`}
              </span>
            );
          })}
        </div>
      ) : (
        <p className="text-hint">Neither run has recorded stage timings.</p>
      )}
      <p className="text-hint">
        Stage timings are observations, not additive percentages. Concurrent source searches
        overlap; differences may reflect different queries, filters, models or workloads.
      </p>
    </section>
  );
}
