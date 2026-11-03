"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";
import type { EvaluationRunSummary } from "@/lib/evaluation-types";
import {
  CHART_BOUNDS,
  qualityChartPoints,
  qualityConfigurations,
  qualityPath,
  type QualityPoint,
  type QualityWindowDays,
} from "@/lib/quality-trend";

interface Props {
  datasetName: string | null;
  nowMs?: number;
  runs: EvaluationRunSummary[];
  loading: boolean;
  error: string;
  hasMore: boolean;
  loadingMore: boolean;
  refresh: () => void;
  loadMore: () => void;
}

const plotBottom = CHART_BOUNDS.height - CHART_BOUNDS.bottom;
const plotRight = CHART_BOUNDS.width - CHART_BOUNDS.right;
const DAY_MS = 24 * 60 * 60 * 1000;

function dateLabel(value: number): string {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function lineLabel(point: QualityPoint): string {
  return (
    new Date(point.timestamp).toLocaleString() +
    " · Recall " +
    (point.run.mean_recall_at_k * 100).toFixed(1) +
    "% · Precision " +
    (point.run.mean_precision_at_k * 100).toFixed(1) +
    "%"
  );
}

function QualityPlot({
  points,
  days,
  nowMs,
}: {
  points: QualityPoint[];
  days: QualityWindowDays;
  nowMs: number;
}) {
  const recall = qualityPath(points, "recallY");
  const precision = qualityPath(points, "precisionY");
  const from = nowMs - days * DAY_MS;
  const first = points[0];
  const last = points[points.length - 1];
  const fill =
    points.length >= 2
      ? recall +
        ` L${last.x.toFixed(2)} ${plotBottom} L${first.x.toFixed(2)} ${plotBottom} Z`
      : "";

  return (
    <>
      <svg
        className="quality-chart"
        viewBox="0 0 600 190"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Measured recall and precision over the last ${days} days from ${points.length} saved benchmark run(s)`}
      >
        <defs>
          <linearGradient id="live-quality-recall-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--accent)" stopOpacity=".2" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((value) => {
          const y = plotBottom - value * (plotBottom - CHART_BOUNDS.top);
          return (
            <g key={value}>
              <path
                className="chart-gridline"
                d={`M${CHART_BOUNDS.left} ${y.toFixed(2)} H${plotRight}`}
              />
              <text x="4" y={y + 4} fill="var(--subtle)" fontSize="10">
                {(value * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}
        {fill ? <path d={fill} fill="url(#live-quality-recall-fill)" /> : null}
        {recall ? <path d={recall} className="quality-real-recall" /> : null}
        {precision ? <path d={precision} className="quality-real-precision" /> : null}
        {points.map((point) => (
          <g key={point.run.run_id}>
            <circle cx={point.x} cy={point.recallY} r="4" fill="var(--accent)">
              <title>{lineLabel(point)}</title>
            </circle>
            <circle cx={point.x} cy={point.precisionY} r="3.5" fill="var(--violet)">
              <title>{lineLabel(point)}</title>
            </circle>
          </g>
        ))}
        <text x={CHART_BOUNDS.left} y="184" fill="var(--subtle)" fontSize="10">
          {dateLabel(from)}
        </text>
        <text
          x={plotRight}
          y="184"
          textAnchor="end"
          fill="var(--subtle)"
          fontSize="10"
        >
          {dateLabel(nowMs)}
        </text>
      </svg>
      <div className="chart-legend">
        <span>
          <i className="legend-line cyan" /> Recall @ K
        </span>
        <span>
          <i className="legend-line purple" /> Precision @ K
        </span>
        <span className="chart-period">{points.length} saved run(s) · {days} days</span>
      </div>
      {points.length === 1 ? (
        <p className="text-hint">
          Only one saved run matches this window and configuration; a trend line needs at least two.
        </p>
      ) : null}
      <p className="text-hint">
        Points are actual persisted benchmark aggregates. Lines connect measurements, not daily
        estimates. Matching configuration and case count do not prove the labeled queries stayed
        identical; use Evaluation run comparison before interpreting a regression.
      </p>
      <ul className="sr-only" aria-label="Recorded run values in chart">
        {points.map((point) => <li key={point.run.run_id}>{lineLabel(point)}</li>)}
      </ul>
    </>
  );
}

export function RetrievalQualityChart({
  datasetName,
  nowMs: suppliedNowMs,
  runs,
  loading,
  error,
  hasMore,
  loadingMore,
  refresh,
  loadMore,
}: Props) {
  const [days, setDays] = useState<QualityWindowDays>(7);
  const [preferredConfig, setPreferredConfig] = useState("");
  const configs = qualityConfigurations(runs);
  const activeConfig = configs.find((config) => config.key === preferredConfig) ?? configs[0];
  const [measuredAt, setMeasuredAt] = useState<number | null>(null);
  useEffect(() => {
    if (suppliedNowMs !== undefined) return;
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setMeasuredAt(Date.now());
    });
    return () => {
      active = false;
    };
  }, [suppliedNowMs]);
  const nowMs = suppliedNowMs ?? measuredAt;
  const points = activeConfig && nowMs !== null
    ? qualityChartPoints(runs, activeConfig.key, days, nowMs)
    : [];

  return (
    <Panel
      title="Retrieval quality over time"
      hint="Measured Recall and Precision from saved benchmark runs"
      action={
        <select
          className="select-control compact"
          aria-label="Chart time window"
          value={days}
          onChange={(event) => setDays(Number(event.target.value) === 30 ? 30 : 7)}
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      }
    >
      {datasetName ? (
        <div className="quality-chart-config">
          <div>
            <span className="field-label">Dataset</span>
            <strong>{datasetName}</strong>
          </div>
          {configs.length > 0 ? (
            <div>
              <label htmlFor="quality-chart-configuration" className="field-label">
                Retrieval configuration
              </label>
              <select
                id="quality-chart-configuration"
                className="select-control"
                value={activeConfig?.key ?? ""}
                onChange={(event) => setPreferredConfig(event.target.value)}
              >
                {configs.map((config) => (
                  <option value={config.key} key={config.key}>
                    {config.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </div>
      ) : null}
      {!datasetName ? (
        <EmptyState
          title="No evaluation dataset"
          description="Create a labeled dataset and run benchmarks to populate the quality graph."
          icon="chart"
          action={<Link href="/evaluations" className="button ghost compact">Open evaluations</Link>}
        />
      ) : loading ? (
        <LoadingState label="Loading benchmark quality history" />
      ) : error ? (
        <ErrorState description={error} onRetry={refresh} />
      ) : nowMs === null ? (
        <LoadingState label="Preparing quality time window" />
      ) : runs.length === 0 ? (
        <EmptyState
          title="No benchmark history yet"
          description="Uploading documents alone does not measure retrieval quality. Add labeled queries and run an evaluation."
          icon="chart"
          action={<Link href="/evaluations" className="button ghost compact">Run evaluation</Link>}
        />
      ) : points.length === 0 ? (
        <EmptyState
          title={"No benchmark runs in the last " + days + " days"}
          description="The selected configuration has no recorded measurements in this time range. Try the other window or a different configuration."
          icon="chart"
          action={<Link href="/evaluations" className="button ghost compact">Open evaluations</Link>}
        />
      ) : (
        <QualityPlot points={points} days={days} nowMs={nowMs} />
      )}
      {datasetName ? (
        <div className="quality-chart-actions">
          <button type="button" className="button ghost compact" onClick={refresh} disabled={loading}>
            Refresh history
          </button>
          {hasMore ? (
            <button type="button" className="button ghost compact" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : "Load older runs"}
            </button>
          ) : null}
          <span className="text-hint">Shows loaded pages only (50 runs per page).</span>
        </div>
      ) : null}
    </Panel>
  );
}
