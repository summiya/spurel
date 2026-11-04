import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StageTimingBreakdown, StageTimingComparison } from "./stage-timings";

describe("measured retrieval stage views", () => {
  it("shows only observed values and does not create fake stages", () => {
    render(<StageTimingBreakdown timings={{ query_embedding: 2.15, vector_search: 4.5 }} />);
    expect(screen.getByText("Query embedding")).toBeInTheDocument();
    expect(screen.getByText("2.1 ms")).toBeInTheDocument();
    expect(screen.getByText("Vector search")).toBeInTheDocument();
    expect(screen.queryByText("Keyword search")).not.toBeInTheDocument();
    expect(screen.getByText(/must not be added together/)).toBeInTheDocument();
  });

  it("treats a historical null snapshot as no measurements", () => {
    render(<StageTimingBreakdown timings={null} />);
    expect(screen.getByText("No stage timings were recorded for this run.")).toBeInTheDocument();
  });

  it("shows A and B timings and only computes measured deltas", () => {
    render(
      <StageTimingComparison
        first={{ vector_search: 4.0, query_embedding: 1.5 }}
        second={{ vector_search: 5.0, rrf_fusion: 0.2 }}
      />,
    );
    expect(screen.getByText(/B − A \+1.0 ms/)).toBeInTheDocument();
    expect(screen.getAllByText(/Δ not available/)).toHaveLength(2);
    expect(screen.getAllByText(/Not recorded/).length).toBeGreaterThan(0);
  });
});
