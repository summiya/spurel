import "server-only";

const MAX_TIMEOUT_MS = 180_000;

export class UpstreamFailure extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

function upstreamSettings() {
  const raw = process.env.SPUREL_BACKEND_URL;
  const token = process.env.SPUREL_API_TOKEN;
  if (!raw || !token || token.length < 32)
    throw new UpstreamFailure(503, "Backend not configured.");
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new UpstreamFailure(503, "Backend URL is invalid.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  ) {
    throw new UpstreamFailure(503, "Backend URL is invalid.");
  }
  return { url, token };
}

export function validUUID(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

export function pageOffset(value: string | null): number | null {
  if (!value) return 0;
  if (!/^(0|[1-9][0-9]{0,7})$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed <= 10_000_000 ? parsed : null;
}

export async function backendRequest(
  path: string,
  init: { method?: "GET" | "POST" | "PUT"; body?: BodyInit; timeoutMs?: number } = {},
): Promise<{ status: number; payload: unknown }> {
  // Every caller constructs a fixed path from validated UUIDs / bounded pagination.
  if (!path.startsWith("/") || path.startsWith("//") || /[#\\]/.test(path)) {
    throw new UpstreamFailure(500, "Invalid upstream path.");
  }
  const { url, token } = upstreamSettings();
  const method = init.method ?? "GET";
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
  if (typeof init.body === "string") headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(new URL(path, url), {
      method,
      body: init.body,
      headers,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(Math.min(MAX_TIMEOUT_MS, init.timeoutMs ?? 15_000)),
    });
  } catch {
    throw new UpstreamFailure(503, "Spurel backend is unavailable.");
  }
  if (response.status >= 300 && response.status < 400) {
    throw new UpstreamFailure(502, "Unexpected backend redirect.");
  }
  if (response.status >= 500) {
    throw new UpstreamFailure(503, "Spurel backend temporarily unavailable.");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new UpstreamFailure(502, "Backend returned an invalid response.");
  }
  if (!response.ok) {
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "The request could not be completed.";
    throw new UpstreamFailure(response.status, detail);
  }
  return { status: response.status, payload };
}

export function safeBackendError(error: unknown): { status: number; error: string } {
  return error instanceof UpstreamFailure
    ? { status: error.status, error: error.message }
    : { status: 503, error: "The request could not be completed." };
}
