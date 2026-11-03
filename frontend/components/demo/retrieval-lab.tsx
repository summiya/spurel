"use client";

import { useMemo, useState, type FormEvent } from "react";

import {
  formatDemoScore,
  PRESETS,
  rankedEvidence,
  type Evidence,
  type RetrievalMode,
} from "@/lib/demo-data";

import { Icon } from "../icons";
import { PageHeading, Panel, ScoreMeter } from "../ui";
import { useDemoToast } from "../workbench-shell";

function HighlightedText({ text }: { text: string }) {
  const match = /passwordless|authentication|refund|backup|restore/i.exec(text);
  if (!match || match.index === undefined) return <>{text}</>;
  const start = match.index;
  const end = start + match[0].length;

  return (
    <>
      {text.slice(0, start)}
      <mark>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  );
}

function EvidenceRow({
  item,
  index,
  mode,
  selected,
  onSelect,
}: {
  item: Evidence;
  index: number;
  mode: RetrievalMode;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={"evidence-result " + (selected ? "selected" : "")}
    >
      <div className="result-heading">
        <span className="result-rank">{String(index + 1).padStart(2, "0")}</span>
        <strong>{item.name}</strong>
        <span className="result-value">{formatDemoScore(item[mode])}</span>
      </div>
      <p>{item.text}</p>
      <div className="tag-row">
        <span className="tag">Chunk {String(item.chunk).padStart(2, "0")}</span>
        <span className="tag">{item.tag}</span>
        <span className="tag">
          {mode === "vector" ? "Cosine" : mode === "keyword" ? "FTS" : "RRF"}
        </span>
      </div>
    </button>
  );
}

export function RetrievalLabPage() {
  const [query, setQuery] = useState(PRESETS[0].query);
  const [submitted, setSubmitted] = useState(PRESETS[0].query);
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [topK, setTopK] = useState(4);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runCount, setRunCount] = useState(0);
  const notify = useDemoToast();

  const evidence = useMemo(() => rankedEvidence(submitted, mode, topK), [submitted, mode, topK]);
  const selected = evidence.find((item) => item.id === selectedId) ?? evidence[0];

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setSubmitted(query.trim());
    setSelectedId(null);
    setRunCount((count) => count + 1);
    notify("Sample retrieval complete · no API request was made.");
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="INTERACTIVE RETRIEVAL EXPLORATION"
        title="Retrieval lab"
        description="Run sample queries, switch retrieval strategies and inspect exactly what made the cut."
        badge="Sample results"
      />

      <Panel
        title="Query composer"
        action={
          <span className="text-hint">
            Knowledge base: <strong>Engineering docs</strong>
          </span>
        }
        className="composer-panel"
      >
        <form onSubmit={submit}>
          <label htmlFor="retrieval-query" className="field-label">
            Question or search query
          </label>
          <textarea
            id="retrieval-query"
            className="textarea-control retrieval-query"
            spellCheck={false}
            placeholder="Ask something about your documents..."
            required
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="presets">
            {PRESETS.map((preset) => (
              <button
                key={preset.topic}
                type="button"
                className="preset-button"
                onClick={() => setQuery(preset.query)}
              >
                <Icon name="arrow-up-right" size={12} /> {preset.label}
              </button>
            ))}
          </div>
          <div className="composer-controls">
            <div className="composer-field">
              <span className="field-label">Retrieval strategy</span>
              <div className="segmented-control" role="group" aria-label="Retrieval strategy">
                {(["hybrid", "vector", "keyword"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={mode === value}
                    className={"segment-button " + (mode === value ? "selected" : "")}
                    onClick={() => {
                      setMode(value);
                      setSelectedId(null);
                    }}
                  >
                    {value[0].toUpperCase() + value.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="topk-field">
              <label htmlFor="retrieval-topk" className="field-label">
                Top K results
              </label>
              <div className="range-control">
                <input
                  id="retrieval-topk"
                  type="range"
                  min="2"
                  max="6"
                  step="1"
                  value={topK}
                  onChange={(event) => {
                    setTopK(Number(event.target.value));
                    setSelectedId(null);
                  }}
                />
                <output htmlFor="retrieval-topk">{topK}</output>
              </div>
            </div>
            <button type="submit" className="button primary submit-retrieval">
              <Icon name="play" size={16} /> Run retrieval
            </button>
          </div>
        </form>
      </Panel>

      <div className="results-grid">
        <Panel
          title="Ranked evidence"
          hint={
            mode[0].toUpperCase() +
            mode.slice(1) +
            " / " +
            evidence.length +
            " illustrative results"
          }
          action={<span className="status-badge">124 ms · sample</span>}
        >
          <div className="evidence-list">
            {evidence.map((item, index) => (
              <EvidenceRow
                key={item.id}
                item={item}
                index={index}
                mode={mode}
                selected={item.id === selected.id}
                onSelect={() => setSelectedId(item.id)}
              />
            ))}
          </div>
        </Panel>

        <Panel
          title="Evidence inspector"
          action={<span className="text-hint">Source details</span>}
        >
          <div className="inspector-head">
            <strong>{selected.name}</strong>
            <small>Document excerpt · Chunk {String(selected.chunk).padStart(2, "0")}</small>
          </div>
          <div className="excerpt-box">
            <HighlightedText text={selected.text} />
          </div>
          <ScoreMeter label="Vector similarity" score={selected.vector} variant="cyan" />
          <ScoreMeter label="Keyword relevance" score={selected.keyword} variant="pink" />
          <ScoreMeter label="Hybrid rank signal" score={selected.hybrid} variant="purple" />
          <div className="inspector-divider" />
          <div className="inspector-facts">
            <span>Source offsets: {selected.offsets}</span>
            <span>Search set: {runCount ? "Demo run #" + runCount : "Initial demo example"}</span>
            <span>Illustrative scores: real cosine, FTS and RRF use different scales.</span>
          </div>
        </Panel>
      </div>
    </div>
  );
}
