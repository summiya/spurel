import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { OperatorLogin } from "@/components/operator-login";
import { OPERATOR_COOKIE, validOperatorSession } from "@/lib/server/operator-session";

export default async function OperatorLoginPage() {
  const cookieJar = await cookies();
  if (validOperatorSession(cookieJar.get(OPERATOR_COOKIE)?.value)) {
    redirect("/knowledge-bases");
  }
  return <OperatorLogin />;
}
