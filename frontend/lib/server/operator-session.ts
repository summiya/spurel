import "server-only";

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import {
  OPERATOR_COOKIE,
  SESSION_TTL_SECONDS,
  issueSession,
  passwordMatches,
  validOperatorSecret,
  verifySession,
} from "@/lib/operator-session-core";

export { OPERATOR_COOKIE, SESSION_TTL_SECONDS };

function credentials() {
  const password = process.env.SPUREL_FRONTEND_OPERATOR_PASSWORD;
  const signingSecret = process.env.SPUREL_FRONTEND_SESSION_SECRET;
  if (!validOperatorSecret(password) || !validOperatorSecret(signingSecret)) return null;
  return { password, signingSecret };
}

export function operatorConfigured(): boolean {
  return credentials() !== null && validOperatorSecret(process.env.SPUREL_API_TOKEN);
}

export function authenticateOperator(candidate: string): string | null {
  const config = credentials();
  if (!config || !operatorConfigured() || !passwordMatches(candidate, config.password)) return null;
  return issueSession(config.signingSecret);
}

export function validOperatorSession(value: string | undefined): boolean {
  const config = credentials();
  return Boolean(config && verifySession(value, config.signingSecret));
}

export function authorizedRequest(request: NextRequest): boolean {
  return validOperatorSession(request.cookies.get(OPERATOR_COOKIE)?.value);
}

export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");
  if (!origin || !host) return false;
  try {
    const parsed = new URL(origin);
    // Next.js may canonicalize request.nextUrl.origin to localhost internally,
    // even when a client used 127.0.0.1. Compare the actual Host header instead.
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      parsed.host.toLowerCase() === host.toLowerCase() &&
      parsed.protocol === request.nextUrl.protocol
    );
  } catch {
    return false;
  }
}

export function authFailure(request: NextRequest, mutation = false): NextResponse | null {
  if (mutation && !sameOrigin(request)) {
    return NextResponse.json({ error: "Cross-origin modification rejected." }, { status: 403 });
  }
  if (!authorizedRequest(request)) {
    return NextResponse.json({ error: "Operator sign-in required." }, { status: 401 });
  }
  return null;
}

export function sessionCookie(request: NextRequest, value: string) {
  return {
    name: OPERATOR_COOKIE,
    value,
    path: "/",
    httpOnly: true as const,
    sameSite: "strict" as const,
    secure: request.nextUrl.protocol === "https:",
    maxAge: SESSION_TTL_SECONDS,
  };
}

export function noStore<T extends NextResponse>(response: T): T {
  response.headers.set("Cache-Control", "no-store");
  return response;
}
