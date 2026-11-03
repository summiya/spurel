import { describe, expect, it } from "vitest";

import {
  issueSession,
  passwordMatches,
  SESSION_TTL_SECONDS,
  validOperatorSecret,
  verifySession,
} from "./operator-session-core";

const password = "operator-password-" + "X".repeat(48);
const secret = "session-secret-" + "Y".repeat(48);

describe("local operator session cryptography", () => {
  it("requires strong independently configured credentials", () => {
    expect(validOperatorSecret(password)).toBe(true);
    expect(validOperatorSecret("weak")).toBe(false);
    expect(validOperatorSecret("a".repeat(32) + " ")).toBe(false);
    expect(passwordMatches(password, password)).toBe(true);
    expect(passwordMatches("incorrect", password)).toBe(false);
    expect(passwordMatches(password, undefined)).toBe(false);
  });

  it("issues an eight-hour, tamper-evident session", () => {
    const start = 1_765_000_000_000;
    const issued = issueSession(secret, start);
    expect(verifySession(issued, secret, start + 60_000)).toBe(true);
    expect(verifySession(issued, secret, start + SESSION_TTL_SECONDS * 1000)).toBe(false);
    expect(verifySession(issued, secret, start - 1_000)).toBe(false);
    expect(verifySession(issued, "another-" + "X".repeat(48), start)).toBe(false);
    expect(
      verifySession(issued.slice(0, -1) + (issued.endsWith("a") ? "b" : "a"), secret, start),
    ).toBe(false);
    expect(verifySession("garbage", secret, start)).toBe(false);
  });

  it("rejects malformed expiration and unsigned payloads", () => {
    const issued = issueSession(secret);
    const parts = issued.split(".");
    expect(verifySession([parts[0], "0000000000", parts[2], parts[3]].join("."), secret)).toBe(
      false,
    );
    expect(verifySession(parts.slice(0, 3).join("."), secret)).toBe(false);
    expect(verifySession("X".repeat(400), secret)).toBe(false);
  });
});
