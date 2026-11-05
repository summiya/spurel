import { type NextRequest, NextResponse } from "next/server";

import { backendRequest, safeBackendError } from "@/lib/server/backend-client";
import { authFailure, noStore } from "@/lib/server/operator-session";

/** Fixed authenticated metadata-only proxy. No secrets or upstream URLs accepted. */
export async function GET(request: NextRequest) {
  const denied = authFailure(request);
  if (denied) return noStore(denied);

  try {
    const result = await backendRequest("/providers/status");
    return noStore(NextResponse.json(result.payload, { status: result.status }));
  } catch (error) {
    const safe = safeBackendError(error);
    return noStore(NextResponse.json({ error: safe.error }, { status: safe.status }));
  }
}
