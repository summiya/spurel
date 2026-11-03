import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RetrievalLabPage } from "./retrieval-lab";

describe("retrieval lab preview", () => {
  it("changes sample evidence after running a refund query", () => {
    const { container } = render(<RetrievalLabPage />);
    expect(screen.getByText("Hybrid / 4 illustrative results")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Refund policy/i }));
    fireEvent.click(screen.getByRole("button", { name: /Run retrieval/i }));

    expect(screen.getAllByText("refund-policy.md").length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll(".evidence-result")).toHaveLength(4);
    expect(screen.getByText(/Sample results/i)).toBeInTheDocument();
  });

  it("supports retrieval modes, Top K and evidence selection", () => {
    const { container } = render(<RetrievalLabPage />);
    fireEvent.click(screen.getByRole("button", { name: "Keyword" }));
    expect(screen.getByText("Keyword / 4 illustrative results")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("slider", { name: /Top K results/i }), {
      target: { value: "2" },
    });
    expect(container.querySelectorAll(".evidence-result")).toHaveLength(2);
    const evidence = container.querySelectorAll(".evidence-result");
    fireEvent.click(evidence[1]);
    expect(evidence[1]).toHaveAttribute("aria-pressed", "true");
    expect(
      within(screen.getByRole("heading", { name: "Evidence inspector" }).closest("section")!)
        .getByText("security-guidelines.md"),
    ).toBeInTheDocument();
  });
});
