import { describe, expect, it } from "vitest";

import {
  formatTraceScore,
  parseTraceComparisonRequest,
  rankMovement,
  traceScoreLabel,
} from "./trace-history-types";

const a = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const b = "d73b06d7-a20e-4ddf-9859-242d69d4372f";

describe("trace history comparison boundary", () => {
  it("allows two distinct valid scoped trace UUIDs only", () => {
    expect(parseTraceComparisonRequest({ first_trace_id: a, second_trace_id: b })).toEqual({
      first_trace_id: a,
      second_trace_id: b,
    });
    for (const bad of [
      null,
      [],
      {},
      "text",
      { first_trace_id: a, second_trace_id: a },
      { first_trace_id: a, second_trace_id: a.toUpperCase() },
      { first_trace_id: a, second_trace_id: "invalid" },
      { first_trace_id: a, second_trace_id: b, redirect: "http://example.com" },
      { first_trace_id: true, second_trace_id: b },
    ]) {
      expect(parseTraceComparisonRequest(bad)).toBeNull();
    }
  });

  it("explains rank delta correctly relative to baseline A", () => {
    expect(rankMovement(-2, 4, 2)).toBe("Up 2");
    expect(rankMovement(3, 2, 5)).toBe("Down 3");
    expect(rankMovement(0, 3, 3)).toBe("Unchanged");
    expect(rankMovement(null, null, 4)).toBe("Only in B");
    expect(rankMovement(null, 3, null)).toBe("Only in A");
    expect(rankMovement(null, 3, 4)).toBe("Unknown");
  });

  it("keeps raw cross-mode score units separate", () => {
    expect(traceScoreLabel("vector")).toBe("Cosine");
    expect(traceScoreLabel("keyword")).toBe("Postgres FTS");
    expect(traceScoreLabel("hybrid")).toBe("RRF");
    expect(formatTraceScore(0, 5)).toBe("0.00000");
    expect(formatTraceScore(null, 4)).toBe("—");
    expect(formatTraceScore(0.032786, 6)).toBe("0.032786");
  });
});
