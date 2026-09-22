import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("renders the Spurel product name and tagline", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Spurel" })).toBeInTheDocument();
    expect(
      screen.getByText("Visual debugging and evaluation for RAG retrieval."),
    ).toBeInTheDocument();
  });
});
