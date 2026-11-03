import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const OPERATOR_COOKIE = "spurel_operator_session";
export const SESSION_TTL_SECONDS = 8 * 60 * 60;
const SESSION_VERSION = "v1";

export function validOperatorSecret(secret: string | undefined): secret is string {
  return Boolean(
    secret &&
      secret.length >= 32 &&
      secret.length <= 512 &&
      /^[\x21-\x7e]+$/.test(secret),
  );
}

export function passwordMatches(candidate: string, configured: string | undefined): boolean {
  if (!validOperatorSecret(configured) || candidate.length > 1024) return false;
  const expected = createHash("sha256").update(configured, "utf8").digest();
  const submitted = createHash("sha256").update(candidate, "utf8").digest();
  return timingSafeEqual(expected, submitted);
}

function mac(secret: string, body: string): string {
  return createHmac("sha256", secret).update(body).digest("base64url");
}

export function issueSession(secret: string, nowMs = Date.now()): string {
  if (!validOperatorSecret(secret)) throw new Error("Invalid session signing secret");
  const expires = Math.floor(nowMs / 1000) + SESSION_TTL_SECONDS;
  const body = `${SESSION_VERSION}.${expires}.${randomBytes(18).toString("base64url")}`;
  return `${body}.${mac(secret, body)}`;
}

export function verifySession(
  value: string | undefined,
  secret: string | undefined,
  nowMs = Date.now(),
): boolean {
  if (!value || value.length > 256 || !validOperatorSecret(secret)) return false;
  const parts = value.split(".");
  if (parts.length !== 4 || parts[0] !== SESSION_VERSION) return false;
  const [, exp, nonce, signature] = parts;
  if (!/^[0-9]{10,11}$/.test(exp) || !/^[A-Za-z0-9_-]{24}$/.test(nonce)) return false;
  if (!/^[A-Za-z0-9_-]{43}$/.test(signature)) return false;
  const current = Math.floor(nowMs / 1000);
  const expires = Number(exp);
  if (!Number.isSafeInteger(expires) || expires <= current || expires > current + SESSION_TTL_SECONDS)
    return false;
  const expected = Buffer.from(mac(secret, parts.slice(0, 3).join(".")));
  const actual = Buffer.from(signature);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
