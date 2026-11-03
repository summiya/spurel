import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LiveEvaluationsPage } from "@/components/live/evaluations";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

export default async function EvaluationsRoute() {
  const cookieJar = await cookies();
  if (!validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) redirect("/operator/login");
  return <LiveEvaluationsPage />;
}
