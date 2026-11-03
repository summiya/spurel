import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Spurel overview", () => {
  it("introduces the approved retrieval-intelligence demo", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "Every retrieval decision. Visible." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Stop guessing why RAG works.")).toBeInTheDocument();
    expect(screen.getByText(/Illustrative performance trend/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Explore retrieval lab/i })).toHaveAttribute(
      "href",
      "/retrieval",
    );
  });
});
