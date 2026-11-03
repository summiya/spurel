import { describe, expect, it } from "vitest";
import { evaluationOperation } from "./evaluation-route-contract";

const validUUID = (id: string) => id === "00000000-0000-4000-8000-000000000001";

describe("SP-14 explicit proxy allowlist", () => {
  it("routes only known scoped evaluations", () => {
    expect(evaluationOperation(["cases"], validUUID, "GET")).toMatchObject({ mode: "read", paginated: true });
    expect(evaluationOperation(["cases"], validUUID, "POST")).toMatchObject({ kind: "case" });
    expect(evaluationOperation(["evaluate", "hybrid"], validUUID, "POST")).toMatchObject({ kind: "hybrid" });
    expect(evaluationOperation(["quality-gates", "evaluate"], validUUID, "POST")).toMatchObject({ kind: "gate" });
    expect(evaluationOperation(["baselines"], validUUID, "PUT")).toMatchObject({ kind: "promote" });
  });
  it("does not forward invented paths, routes or methods", () => {
    for (const parts of [
      ["..", "secrets"], ["evaluate", "bm25"], ["evaluate", "hybrid", "extra"],
      ["runs", "other"], ["baselines", "resolve"], ["health"], ["cases", "other"],
    ]) expect(evaluationOperation(parts, validUUID, "POST")).toBeNull();
    expect(evaluationOperation(["cases"], validUUID, "DELETE")).toBeNull();
    expect(evaluationOperation(["runs", "bad"], validUUID, "GET")).toBeNull();
    expect(evaluationOperation(["runs", "00000000-0000-4000-8000-000000000001"], validUUID, "GET")).not.toBeNull();
  });
});
