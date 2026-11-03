import { describe, expect, it } from "vitest";

import { formatDemoScore, rankedEvidence, topicForQuery } from "./demo-data";

describe("demo data boundaries", () => {
  it("selects the correct sample topic by query", () => {
    expect(topicForQuery("How does passwordless login work?")).toBe("auth");
    expect(topicForQuery("Can customers request a refund?")).toBe("refund");
    expect(topicForQuery("Restore the database from backup")).toBe("backup");
  });

  it("orders each mode by its own score and respects Top K", () => {
    for (const mode of ["hybrid", "vector", "keyword"] as const) {
      const results = rankedEvidence("refund approval", mode, 3);
      expect(results).toHaveLength(3);
      expect(results[0].name).toBe("refund-policy.md");
      expect(results[0][mode]).toBeGreaterThanOrEqual(results[1][mode]);
      expect(results[1][mode]).toBeGreaterThanOrEqual(results[2][mode]);
    }
  });

  it("clamps sample result counts to the bounds of fixtures", () => {
    expect(rankedEvidence("auth", "vector", 999)).toHaveLength(6);
    expect(rankedEvidence("auth", "vector", -20)).toHaveLength(1);
    expect(formatDemoScore(0.943)).toBe("94.3%");
  });
});
