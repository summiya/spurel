import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveRetrievalLabPage } from "@/components/live/retrieval-lab";
import { validUUID } from "@/lib/server/backend-client";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

type Params = { kb?: string | string[] };

export default async function RetrievalLabRoute({
  searchParams,
}: {
  searchParams: Promise<Params>;
}) {
  const cookieJar = await cookies();
  if (!validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/operator/login");
  }
  const params = await searchParams;
  const initialKnowledgeBaseId =
    typeof params.kb === "string" && validUUID(params.kb) ? params.kb : undefined;
  return <LiveRetrievalLabPage initialKnowledgeBaseId={initialKnowledgeBaseId} />;
}
