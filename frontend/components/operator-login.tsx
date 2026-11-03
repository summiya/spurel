"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/icons";

export function OperatorLogin() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/operator/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) {
        const payload: unknown = await response.json();
        const message =
          payload &&
          typeof payload === "object" &&
          "error" in payload &&
          typeof payload.error === "string"
            ? payload.error
            : "Sign-in failed.";
        throw new Error(message);
      }
      setPassword("");
      router.replace("/knowledge-bases");
      router.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="operator-container">
      <div className="operator-head">
        <span className="kb-card-icon">
          <Icon name="shield" size={26} />
        </span>
        <span className="status-badge">LOCAL OPERATOR ACCESS</span>
      </div>
      <h1>Connect to your Spurel workspace</h1>
      <p>
        Sign in to manage real knowledge bases and documents. Retrieval and evaluation screens
        remain clearly labeled demos for now.
      </p>
      <form onSubmit={submit} className="operator-form">
        <label htmlFor="operator-password" className="field-label">
          Local operator password
        </label>
        <input
          id="operator-password"
          type="password"
          autoComplete="current-password"
          className="input-control"
          placeholder="Enter the local operator password"
          minLength={32}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error ? (
          <p className="operator-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" className="button primary" disabled={busy || password.length < 32}>
          <Icon name="shield" size={15} />
          {busy ? "Signing in…" : "Unlock live workspace"}
        </button>
      </form>
      <div className="inline-notice">
        <Icon name="info" size={17} />
        From your Spurel root directory, view your local password with
        <code>{"grep '^SPUREL_FRONTEND_OPERATOR_PASSWORD=' .env"}</code>. Keep it private. Your
        backend API token never enters the browser.
      </div>
      <p className="text-hint">A signed, HTTP-only operator session expires after eight hours.</p>
    </div>
  );
}
