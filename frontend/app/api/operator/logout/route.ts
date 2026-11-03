import { type NextRequest, NextResponse } from "next/server";

import { noStore, OPERATOR_COOKIE, sameOrigin } from "@/lib/server/operator-session";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) {
    return noStore(NextResponse.json({ error: "Cross-origin sign-out rejected." }, { status: 403 }));
  }
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set({
    name: OPERATOR_COOKIE,
    value: "",
    path: "/",
    sameSite: "strict",
    httpOnly: true,
    secure: request.nextUrl.protocol === "https:",
    maxAge: 0,
  });
  return noStore(response);
}
