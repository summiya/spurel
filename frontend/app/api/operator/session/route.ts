import { type NextRequest, NextResponse } from "next/server";

import {
  authorizedRequest,
  noStore,
  operatorConfigured,
} from "@/lib/server/operator-session";

export async function GET(request: NextRequest) {
  return noStore(
    NextResponse.json({
      configured: operatorConfigured(),
      authenticated: authorizedRequest(request),
    }),
  );
}
