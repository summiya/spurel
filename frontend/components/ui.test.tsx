import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ErrorState, LoadingState } from "./ui";

describe("reusable async states", () => {
  it("labels an empty view accessibly", () => {
    render(<EmptyState title="Nothing indexed" description="Upload a document to begin." />);
    expect(screen.getByRole("status")).toHaveTextContent("Nothing indexed");
  });

  it("provides an actionable retry for failures", () => {
    const retry = vi.fn();
    render(<ErrorState description="The demo could not render." onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("announces loading in a live region", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });
});
