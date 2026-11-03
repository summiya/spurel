import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveRagAnswersPage } from "@/components/live/rag-answers";
import { validUUID } from "@/lib/server/backend-client";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

type SearchParams = { kb?: string | string[] };

export default async function RagAnswersRoute({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const jar = await cookies();
  if (!validOperatorSession(jar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/operator/login");
  }

  const params = await searchParams;
  const initialKnowledgeBaseId =
    typeof params.kb === "string" && validUUID(params.kb) ? params.kb : undefined;

  return <LiveRagAnswersPage initialKnowledgeBaseId={initialKnowledgeBaseId} />;
}
