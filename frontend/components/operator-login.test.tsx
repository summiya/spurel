import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { OperatorLogin } from "./operator-login";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

describe("operator sign-in", () => {
  beforeEach(() => {
    navigation.replace.mockClear();
    navigation.refresh.mockClear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("never writes the operator password to browser storage", async () => {
    localStorage.clear();
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ authenticated: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    render(<OperatorLogin />);
    fireEvent.change(screen.getByLabelText("Local operator password"), {
      target: { value: "a".repeat(48) },
    });
    fireEvent.click(screen.getByRole("button", { name: /Unlock live workspace/i }));
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/knowledge-bases"));
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][1]).toMatchObject({
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    expect(localStorage.length).toBe(0);
  });

  it("shows a generic auth error without redirecting", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ error: "Invalid operator credentials." }), { status: 401 }),
        ),
    );
    render(<OperatorLogin />);
    fireEvent.change(screen.getByLabelText("Local operator password"), {
      target: { value: "invalid-".repeat(6) },
    });
    fireEvent.click(screen.getByRole("button", { name: /Unlock live workspace/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid operator credentials.");
    expect(navigation.replace).not.toHaveBeenCalled();
  });
});
