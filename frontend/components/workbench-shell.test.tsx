import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkbenchShell } from "./workbench-shell";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: navigation.push }),
}));

describe("workbench shell", () => {
  beforeEach(() => {
    navigation.push.mockClear();
    localStorage.clear();
    document.documentElement.dataset.theme = "dark";
  });

  it("has responsive navigation with a live home status", () => {
    render(
      <WorkbenchShell>
        <p>Workspace content</p>
      </WorkbenchShell>,
    );
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Retrieval lab/i })).toHaveAttribute(
      "href",
      "/retrieval",
    );
    expect(screen.getByText(/LIVE WORKSPACE/)).toBeInTheDocument();
    expect(screen.queryByText("58%")).not.toBeInTheDocument();
  });

  it("opens command search and navigates with keyboard", () => {
    render(
      <WorkbenchShell>
        <p>Workspace content</p>
      </WorkbenchShell>,
    );
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    const dialog = screen.getByRole("dialog", { name: /Jump to a Spurel page/i });
    expect(dialog).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Search pages" }), {
      target: { value: "trace" },
    });
    fireEvent.keyDown(dialog, { key: "Enter" });
    expect(navigation.push).toHaveBeenCalledWith("/traces");
  });

  it("toggles light and dark themes without storing backend secrets", () => {
    render(
      <WorkbenchShell>
        <p>Workspace content</p>
      </WorkbenchShell>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("spurel-theme")).toBe("light");
    expect(localStorage.getItem("SPUREL_API_TOKEN")).toBeNull();
  });
});
