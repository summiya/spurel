import { type NextRequest, NextResponse } from "next/server";

import {
  authenticateOperator,
  noStore,
  operatorConfigured,
  sameOrigin,
  sessionCookie,
} from "@/lib/server/operator-session";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) {
    return noStore(NextResponse.json({ error: "Cross-origin sign-in rejected." }, { status: 403 }));
  }
  if (!operatorConfigured()) {
    return noStore(
      NextResponse.json({ error: "Operator sign-in is not configured." }, { status: 503 }),
    );
  }
  if (Number(request.headers.get("content-length") ?? 0) > 4096) {
    return noStore(NextResponse.json({ error: "Sign-in request is too large." }, { status: 413 }));
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return noStore(NextResponse.json({ error: "Invalid sign-in request." }, { status: 400 }));
  }
  const password =
    body && typeof body === "object" && "password" in body && typeof body.password === "string"
      ? body.password
      : "";
  const session = authenticateOperator(password);
  if (!session) {
    return noStore(NextResponse.json({ error: "Invalid operator credentials." }, { status: 401 }));
  }
  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(sessionCookie(request, session));
  return noStore(response);
}
