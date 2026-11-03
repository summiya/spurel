import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveChunkInspectorPage } from "@/components/live/chunk-inspector";
import { validUUID } from "@/lib/server/backend-client";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

type SearchQuery = {
  kb?: string | string[];
  doc?: string | string[];
};

export default async function ChunkInspectorRoute({
  searchParams,
}: {
  searchParams: Promise<SearchQuery>;
}) {
  const cookieJar = await cookies();
  if (!validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/operator/login");
  }

  const query = await searchParams;
  const initialKnowledgeBaseId =
    typeof query.kb === "string" && validUUID(query.kb) ? query.kb : undefined;
  const initialDocumentId =
    typeof query.doc === "string" && validUUID(query.doc) ? query.doc : undefined;

  return (
    <LiveChunkInspectorPage
      initialKnowledgeBaseId={initialKnowledgeBaseId}
      initialDocumentId={initialDocumentId}
    />
  );
}
