import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveTraceHistoryPage } from "@/components/live/traces";
import { validUUID } from "@/lib/server/backend-client";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

type SearchQuery = { kb?: string | string[]; trace?: string | string[] };

export default async function TraceHistoryRoute({
  searchParams,
}: {
  searchParams: Promise<SearchQuery>;
}) {
  const cookieJar = await cookies();
  if (!validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/operator/login");
  }
  const params = await searchParams;
  const initialKnowledgeBaseId = typeof params.kb === "string" && validUUID(params.kb)
    ? params.kb : undefined;
  const initialTraceId = typeof params.trace === "string" && validUUID(params.trace)
    ? params.trace : undefined;
  return (
    <LiveTraceHistoryPage
      initialKnowledgeBaseId={initialKnowledgeBaseId}
      initialTraceId={initialTraceId}
    />
  );
}
