import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KnowledgeBasesPage } from "./knowledge-bases";

describe("knowledge bases preview", () => {
  it("creates a local demo-only collection without claiming server persistence", () => {
    render(<KnowledgeBasesPage />);
    fireEvent.click(screen.getByRole("button", { name: /New knowledge base/i }));
    expect(screen.getByRole("dialog", { name: /New demo knowledge base/i })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: /Collection name/i }), {
      target: { value: "Architecture reference" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create in preview/i }));

    expect(screen.getByRole("button", { name: /Architecture reference/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/Empty collection created for this local preview/i).length,
    ).toBeGreaterThan(0);
  });
});
