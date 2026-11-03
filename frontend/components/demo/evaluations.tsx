"use client";

import { useMemo, useState } from "react";

import { DEMO_RUNS } from "@/lib/demo-data";

import { Icon } from "../icons";
import { MetricCard, PageHeading, Panel } from "../ui";
import { useDemoToast } from "../workbench-shell";

type Run = (typeof DEMO_RUNS)[number];
type Filter = "all" | "passed" | "review";

export function EvaluationsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string>(DEMO_RUNS[0].id);
  const [demoRuns, setDemoRuns] = useState<Array<Run | {
    id: string;
    name: string;
    mode: string;
    recall: number;
    precision: number;
    mrr: number;
    status: string;
    date: string;
  }>>([...DEMO_RUNS]);
  const notify = useDemoToast();

  const visible = useMemo(() => demoRuns.filter((run) =>
    filter === "all" || run.status.toLowerCase() === filter
  ), [demoRuns, filter]);
  const current = demoRuns.find((run) => run.id === selectedId) ?? visible[0] ?? demoRuns[0];

  function runSampleBenchmark() {
    const next = {
      id: "DEMO-" + (demoRuns.length + 1).toString().padStart(3, "0"),
      name: "Preview retrieval regression",
      mode: "Hybrid",
      recall: 92.4,
      precision: 86.8,
      mrr: 0.91,
      status: "Passed",
      date: "Just now",
    };
    setDemoRuns((items) => [next, ...items]);
    setSelectedId(next.id);
    setFilter("all");
    notify("Sample benchmark added locally · no API request made.");
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="MEASURE WHAT MATTERS"
        title="Evaluations"
        description="See retrieval quality, compare benchmark runs and spot regressions."
        badge="Illustrative metrics"
        action={
          <button type="button" className="button primary" onClick={runSampleBenchmark}>
            <Icon name="play" size={15} /> Run sample benchmark
          </button>
        }
      />

      <div className="metrics-grid">
        <MetricCard label="Recall @ 10" value="91.8%" description="↑ 3.6% from sample baseline" icon="chart" />
        <MetricCard label="Precision @ 10" value="87.4%" description="↑ 2.1% from sample baseline" icon="filter" />
        <MetricCard label="Mean reciprocal rank" value="0.92" description="Rank quality · demo" icon="layers" />
        <MetricCard label="Benchmark runs" value={String(demoRuns.length).padStart(2, "0")} description="Local preview records only" icon="clock" direction="neutral" />
      </div>

      <div className="dashboard-grid">
        <Panel title="Quality across experiments" hint="Demonstration comparison, not backend measurements">
          <div className="evaluation-bars">
            {[
              { label: "Hybrid + RRF", value: 92, tone: "cyan" },
              { label: "Vector search", value: 87, tone: "purple" },
              { label: "Keyword search", value: 81, tone: "pink" },
            ].map((bar) => (
              <div className="evaluation-bar-row" key={bar.label}>
                <span>{bar.label}</span>
                <div className="evaluation-bar-track">
                  <div className={"evaluation-bar-fill " + bar.tone} style={{ width: bar.value + "%" }} />
                </div>
                <strong>{bar.value}%</strong>
              </div>
            ))}
          </div>
          <p className="text-hint">Illustrative recall comparison. Source modes use different ranking methods.</p>
        </Panel>
        <Panel title="Judgment integrity" hint="Preflight checks against the active index">
          <div className="integrity-state">
            <span className="integrity-icon"><Icon name="shield" size={26} /></span>
            <div><strong>Sample dataset labels are valid</strong><p>Example only. Live judgment audits require a connected backend.</p></div>
          </div>
          <div className="pipeline-detail"><span>Inactive judgments</span><strong>0 · demo</strong></div>
          <div className="pipeline-detail last"><span>Missing evidence labels</span><strong>0 · demo</strong></div>
        </Panel>
      </div>

      <Panel
        title="Recent benchmark runs"
        hint="Select a run to inspect its sample metrics"
        action={
          <div className="segmented-control compact" role="group" aria-label="Run status filter">
            {(["all", "passed", "review"] as const).map((value) => (
              <button
                type="button"
                key={value}
                aria-pressed={filter === value}
                className={"segment-button " + (filter === value ? "selected" : "")}
                onClick={() => setFilter(value)}
              >
                {value === "all" ? "All" : value === "passed" ? "Passed" : "Review"}
              </button>
            ))}
          </div>
        }
      >
        <div className="responsive-table">
          <table className="data-table">
            <thead><tr><th>Run</th><th>Mode</th><th>Recall</th><th>Precision</th><th>MRR</th><th>Status</th><th>When</th></tr></thead>
            <tbody>
              {visible.map((run) => (
                <tr key={run.id} className={selectedId === run.id ? "selected" : ""}>
                  <td>
                    <button type="button" className="table-link" onClick={() => setSelectedId(run.id)}>
                      {run.name}
                    </button>
                    <small className="table-subline">{run.id}</small>
                  </td>
                  <td>{run.mode}</td>
                  <td>{run.recall.toFixed(1)}%</td>
                  <td>{run.precision.toFixed(1)}%</td>
                  <td>{run.mrr.toFixed(2)}</td>
                  <td><span className={"status-badge " + (run.status === "Passed" ? "success" : "warn")}>{run.status}</span></td>
                  <td>{run.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {visible.length === 0 ? <p className="table-empty">No sample runs match this filter.</p> : null}
        <div className="selected-run">
          <Icon name="chart" size={18} />
          <div>
            <strong>{current.name}</strong>
            <p>{current.mode} retrieval · {current.recall.toFixed(1)}% recall · {current.mrr.toFixed(2)} MRR</p>
          </div>
          <span className="status-badge">Preview</span>
        </div>
      </Panel>
    </div>
  );
}
