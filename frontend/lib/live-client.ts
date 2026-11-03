import type { Page } from "@/lib/live-types";

export class WorkspaceError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function workspaceFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    cache: "no-store",
  });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    throw new WorkspaceError(502, "The workspace returned an invalid response.");
  }
  if (!response.ok) {
    const error =
      payload &&
      typeof payload === "object" &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : "The operation failed.";
    throw new WorkspaceError(response.status, error);
  }
  return payload as T;
}

export function isPage<T>(value: unknown): value is Page<T> {
  return (
    value !== null &&
    typeof value === "object" &&
    "items" in value &&
    Array.isArray(value.items) &&
    "offset" in value &&
    typeof value.offset === "number" &&
    "limit" in value &&
    typeof value.limit === "number"
  );
}

export function liveError(cause: unknown): string {
  if (cause instanceof WorkspaceError && cause.status === 401) {
    return "Your operator session has expired. Sign in again to resume.";
  }
  return cause instanceof Error ? cause.message : "Unable to complete the request.";
}
