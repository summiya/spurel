import "server-only";

type HealthStatus = "online" | "offline" | "unconfigured";

function upstreamBase(): URL | null {
  const raw = process.env.SPUREL_BACKEND_URL;
  if (!raw) return null;

  const url = new URL(raw);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("SPUREL_BACKEND_URL must be an HTTP(S) URL");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("SPUREL_BACKEND_URL cannot contain credentials or query parameters");
  }
  return url;
}

/**
 * Only a public health check is wired in SP-09. Do not expose a generic bearer-
 * token proxy to anonymous browser users. The shared SPUREL_API_TOKEN must be
 * used from authenticated server-only code after a frontend auth boundary exists.
 */
export async function readPublicBackendHealth(): Promise<HealthStatus> {
  const base = upstreamBase();
  if (!base) return "unconfigured";
  try {
    const response = await fetch(new URL("/health", base), {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return response.ok ? "online" : "offline";
  } catch {
    return "offline";
  }
}
