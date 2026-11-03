import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChunkInspectorPage } from "./chunk-inspector";

describe("chunk inspector preview", () => {
  it("switches documents and allows historical version inspection", () => {
    render(<ChunkInspectorPage />);

    fireEvent.click(screen.getByRole("button", { name: /security-guidelines.md/i }));
    expect(screen.getByRole("heading", { name: "security-guidelines.md" })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Chunk version" }), {
      target: { value: "1" },
    });
    expect(screen.getByText(/Historical sample snapshot/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Chunk version" })).toHaveValue("1");
  });
});
