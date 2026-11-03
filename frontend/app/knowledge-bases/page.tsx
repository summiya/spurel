import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveKnowledgeBasesPage } from "@/components/live/knowledge-bases";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

export default async function KnowledgeBasesRoute() {
  const cookieJar = await cookies();
  if (!validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/operator/login");
  }
  return <LiveKnowledgeBasesPage />;
}
