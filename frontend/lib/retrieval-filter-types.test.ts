import { describe, expect, it } from "vitest";

import {
  describeRetrievalFilters,
  parseRetrievalMetadataFilters,
  retrievalFiltersKey,
} from "./retrieval-filter-types";

const document = "d98d2800-9df4-4f98-a397-0d0fd19ee032";
const second = "d73b06d7-a20e-4ddf-9859-242d69d4372f";

describe("SP-19 metadata filter payloads", () => {
  it("accepts typed document criteria and normalizes dates without extra keys", () => {
    expect(
      parseRetrievalMetadataFilters({
        document_ids: [document],
        media_types: ["application/pdf"],
        filename_contains: "  100%_guide  ",
        created_after: "2026-10-01T00:00:00Z",
        created_before: "2026-11-04T23:59:59.999Z",
      }),
    ).toEqual({
      document_ids: [document],
      media_types: ["application/pdf"],
      filename_contains: "100%_guide",
      created_after: "2026-10-01T00:00:00.000Z",
      created_before: "2026-11-04T23:59:59.999Z",
    });
  });

  it("rejects open-ended, duplicate, unrecognized and dangerous criteria", () => {
    for (const bad of [
      null, [], {}, { document_ids: [] },
      { document_ids: ["not-uuid"] },
      { document_ids: [document, document.toUpperCase()] },
      { document_ids: Array(21).fill(document) },
      { media_types: ["text/html"] },
      { media_types: ["text/plain", "text/plain"] },
      { filename_contains: "   " },
      { filename_contains: "a".repeat(101) },
      { filename_contains: "abc\x00def" },
      { created_after: "2026-11-04" },
      { created_before: "2026-01-01T00:00:00" },
      { created_after: "2026-11-04T00:00:00Z", created_before: "2026-11-03T00:00:00Z" },
      { filename_contains: "policy", custom_sql: "DROP TABLE documents" },
    ]) {
      expect(parseRetrievalMetadataFilters(bad)).toBeNull();
    }
  });

  it("compares filters independently of field order and distinguishes changes", () => {
    const first = parseRetrievalMetadataFilters({
      media_types: ["text/plain"], document_ids: [document, second],
    });
    const same = parseRetrievalMetadataFilters({
      document_ids: [second, document], media_types: ["text/plain"],
    });
    expect(retrievalFiltersKey(first)).toBe(retrievalFiltersKey(same));
    expect(retrievalFiltersKey(first)).not.toBe(retrievalFiltersKey(null));
    expect(describeRetrievalFilters(null)).toMatch(/All active documents/);
    expect(describeRetrievalFilters(first)).toMatch(/2 document\(s\)/);
  });

  it("accepts server response nulls for unspecified fields without inventing filters", () => {
    expect(parseRetrievalMetadataFilters({
      document_ids: [],
      media_types: ["application/pdf"],
      filename_contains: null,
      created_after: null,
      created_before: null,
    })).toEqual({ media_types: ["application/pdf"] });
  });
});
