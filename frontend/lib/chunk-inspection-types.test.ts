import { describe, expect, it } from "vitest";

import { parseChunkVersion } from "./chunk-inspection-types";

describe("chunk version input validation", () => {
  it("uses null to select the current active index", () => {
    expect(parseChunkVersion(null)).toBeNull();
  });

  it("accepts bounded positive versions only", () => {
    expect(parseChunkVersion("1")).toBe(1);
    expect(parseChunkVersion("40")).toBe(40);
    expect(parseChunkVersion("999999")).toBe(999999);
  });

  it("rejects malformed and path-injection values", () => {
    for (const invalid of ["", "0", "01", "-1", "1/2", "1%2F2", "1?x=y", "1.0", "1000000"]) {
      expect(parseChunkVersion(invalid)).toBeUndefined();
    }
  });
});
