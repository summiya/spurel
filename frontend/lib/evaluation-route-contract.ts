import { isEvaluationMode } from "@/lib/evaluation-types";

export type EvaluationOperation =
  | { mode: "read"; suffix: string; paginated: boolean }
  | { mode: "write"; suffix: string; kind: string; method: "POST" | "PUT" };

/** Only these exact backend operations may be reached through the operator proxy. */
export function evaluationOperation(
  parts: string[],
  validUUID: (value: string) => boolean,
  method: string,
): EvaluationOperation | null {
  if (parts.length === 0) return null;
  const [section, ...rest] = parts;
  const relative = parts.join("/");
  if (method === "GET") {
    if (["cases", "runs", "baselines", "baselines/history"].includes(relative))
      return { mode: "read", suffix: relative, paginated: true };
    if (relative === "judgment-audit") return { mode: "read", suffix: relative, paginated: false };
    if ((section === "cases" || section === "runs") && rest.length === 1 && validUUID(rest[0]))
      return { mode: "read", suffix: relative, paginated: false };
    return null;
  }
  if (method === "POST") {
    if (relative === "cases")
      return { mode: "write", suffix: relative, kind: "case", method: "POST" };
    if (section === "evaluate" && rest.length === 1 && isEvaluationMode(rest[0]))
      return { mode: "write", suffix: relative, kind: rest[0], method: "POST" };
    if (relative === "run-comparisons")
      return { mode: "write", suffix: relative, kind: "compare", method: "POST" };
    if (relative === "quality-gates/evaluate")
      return { mode: "write", suffix: relative, kind: "gate", method: "POST" };
  }
  if (method === "PUT" && relative === "baselines")
    return { mode: "write", suffix: relative, kind: "promote", method: "PUT" };
  return null;
}
