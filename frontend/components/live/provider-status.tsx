"use client";

import { useEffect, useState } from "react";

import {
  isProviderStatus,
  providerName,
  type ProviderState,
  type ProviderStatus,
} from "@/lib/provider-status-types";
import { workspaceFetch } from "@/lib/live-client";

function description(state: ProviderState): string {
  const model = state.model ?? "No model selected";
  return `${providerName(state.provider)} · ${model} · ${state.configured ? "Configured" : "Needs server configuration"}`;
}

/** Read-only server configuration; a GET never probes or runs any model. */
export function ProviderStatusPanel({ purpose }: { purpose: "embedding" | "generation" | "both" }) {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void workspaceFetch<unknown>("/api/workspace/providers/status")
      .then((data) => {
        if (cancelled) return;
        if (isProviderStatus(data)) setStatus(data);
        else setError(true);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="inline-notice" aria-label="Selected model providers">
      {status ? (
        <div>
          {(purpose === "embedding" || purpose === "both") && (
            <p>
              <strong>Embedding provider:</strong> {description(status.embedding)}
              {status.embedding.dimensions ? ` · ${status.embedding.dimensions} dimensions` : ""}
            </p>
          )}
          {(purpose === "generation" || purpose === "both") && (
            <p>
              <strong>Generation provider:</strong> {description(status.generation)}
            </p>
          )}
          <p className="text-hint">
            Server-only configuration, not a connectivity test. Set providers in the backend
            environment and restart it. Switching embedding spaces requires explicitly
            reprocessing documents; previous indexed versions remain intact.
          </p>
        </div>
      ) : (
        <p className="text-hint">
          {error
            ? "Provider configuration details are unavailable."
            : "Reading configured model providers (no model calls)…"}
        </p>
      )}
    </section>
  );
}
