import type { ReactNode } from "react";

import { Icon, type IconName } from "./icons";

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
  badge,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  badge?: string;
}) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      <div className="page-actions">
        {badge ? <span className="demo-pill">{badge}</span> : null}
        {action}
      </div>
    </div>
  );
}

export function Panel({
  title,
  hint,
  action,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"panel " + className}>
      <header className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          {hint ? <p className="panel-hint">{hint}</p> : null}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  description,
  icon,
  direction = "positive",
}: {
  label: string;
  value: string;
  description: string;
  icon: IconName;
  direction?: "positive" | "neutral";
}) {
  return (
    <div className="metric-card">
      <div className="metric-heading">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon name={icon} size={17} />
        </span>
      </div>
      <div className="metric-number">{value}</div>
      <p className={direction === "positive" ? "metric-note positive" : "metric-note"}>
        {description}
      </p>
    </div>
  );
}

export function SampleBadge({ children = "Sample data" }: { children?: ReactNode }) {
  return <span className="demo-pill">{children}</span>;
}

export function EmptyState({
  title,
  description,
  icon = "search",
  action,
}: {
  title: string;
  description: string;
  icon?: IconName;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-icon">
        <Icon name={icon} size={23} />
      </span>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
}: {
  title?: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <div className="empty-state error-state" role="alert">
      <span className="empty-icon">
        <Icon name="alert" size={23} />
      </span>
      <strong>{title}</strong>
      <p>{description}</p>
      {onRetry ? (
        <button type="button" className="button ghost" onClick={onRetry}>
          <Icon name="refresh" size={15} /> Try again
        </button>
      ) : null}
    </div>
  );
}

export function ScoreMeter({
  label,
  score,
  variant = "cyan",
}: {
  label: string;
  score: number;
  variant?: "cyan" | "purple" | "pink";
}) {
  return (
    <div className="score-meter">
      <div className="score-meter-head">
        <span>{label}</span>
        <strong>{(score * 100).toFixed(1)}%</strong>
      </div>
      <div className="score-track">
        <span
          className={"score-fill " + variant}
          style={{ width: Math.max(0, Math.min(100, score * 100)) + "%" }}
        />
      </div>
    </div>
  );
}
