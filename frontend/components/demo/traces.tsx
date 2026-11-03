"use client";

import { useMemo, useState } from "react";

import { DEMO_TRACES, rankedEvidence } from "@/lib/demo-data";

import { Icon } from "../icons";
import { EmptyState, PageHeading, Panel, ScoreMeter } from "../ui";

export function TracesPage() {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string>(DEMO_TRACES[0].id);

  const filtered = useMemo(() => DEMO_TRACES.filter((trace) =>
    (trace.query + " " + trace.mode + " " + trace.kb)
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  ), [query]);

  const active = DEMO_TRACES.find((trace) => trace.id === selectedId) ?? DEMO_TRACES[0];
  const evidence = rankedEvidence(active.query, active.mode, active.count);

  return (
    <div className="screen">
      <PageHeading
        eyebrow="RETRIEVAL OBSERVABILITY"
        title="Trace history"
        description="Explore a query, its retrieval strategy and the evidence that reached the top ranks."
        badge="Sample traces"
      />

      <div className="trace-grid">
        <Panel
          title="Saved retrievals"
          hint="Search and select an illustrative trace"
          action={
            <label className="inline-search">
              <Icon name="search" size={16} />
              <span className="sr-only">Filter traces</span>
              <input
                type="search"
                aria-label="Filter traces"
                placeholder="Filter traces"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          }
        >
          {filtered.length ? (
            <div className="trace-list">
              {filtered.map((trace) => (
                <button
                  type="button"
                  key={trace.id}
                  className={"trace-row " + (trace.id === active.id ? "active" : "")}
                  aria-pressed={trace.id === active.id}
                  onClick={() => setSelectedId(trace.id)}
                >
                  <span className="trace-icon"><Icon name="search" size={17} /></span>
                  <span className="trace-content">
                    <strong>{trace.query}</strong>
                    <small>{trace.id} · {trace.mode} · {trace.ago}</small>
                  </span>
                  <span className="trace-duration">{trace.ms} ms</span>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No matching traces" description="Try a different query or retrieval mode." />
          )}
        </Panel>
        <Panel title="Trace details" hint="Snapshot of the selected demo query">
          <div className="trace-detail-top">
            <span className="status-badge">{active.id}</span>
            <span className="status-badge success">{active.mode}</span>
          </div>
          <h3 className="trace-query-title">{active.query}</h3>
          <div className="trace-stat-grid">
            <span><strong>{active.count}</strong><small>Results</small></span>
            <span><strong>{active.ms} ms</strong><small>Latency</small></span>
            <span><strong>{active.kb}</strong><small>Collection</small></span>
          </div>
          <h3 className="subsection-title">Top retrieved evidence</h3>
          <div className="trace-evidence">
            {evidence.slice(0, 3).map((item, index) => (
              <div className="trace-evidence-row" key={item.id}>
                <span className="result-rank">{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{item.name}</strong><small>Chunk {item.chunk} · {item.tag}</small></div>
                <span>{(item[active.mode] * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <ScoreMeter label="Top rank signal" score={evidence[0]?.[active.mode] ?? 0} />
          <p className="text-hint">IDs, timings and rankings are sample data, not persisted traces.</p>
        </Panel>
      </div>
    </div>
  );
}
