"use client";

import { useState } from "react";

import { DEMO_DOCUMENTS } from "@/lib/demo-data";

import { Icon } from "../icons";
import { PageHeading, Panel, ScoreMeter } from "../ui";

export function ChunkInspectorPage() {
  const [documentIndex, setDocumentIndex] = useState(0);
  const [version, setVersion] = useState(2);
  const [chunkIndex, setChunkIndex] = useState(0);
  const document = DEMO_DOCUMENTS[documentIndex];
  const chunks =
    version === document.versions
      ? document.chunks
      : document.chunks.map((chunk, index) =>
          index === 0
            ? chunk
                .replace("A passwordless", "The passwordless")
                .replace("Refunds", "Eligible refunds")
            : chunk,
        );
  const activeChunk = chunks[chunkIndex] ?? chunks[0];

  function selectDocument(index: number) {
    setDocumentIndex(index);
    setVersion(DEMO_DOCUMENTS[index].versions);
    setChunkIndex(0);
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="DOCUMENT INTELLIGENCE"
        title="Chunk inspector"
        description="Explore persisted excerpts, source offsets, versions and embedding availability."
        badge="Read-only demo"
      />
      <div className="chunk-layout">
        <Panel title="Documents" hint="Select a document to inspect its chunks.">
          <div className="document-list">
            {DEMO_DOCUMENTS.map((item, index) => (
              <button
                type="button"
                key={item.id}
                className={"document-item " + (documentIndex === index ? "active" : "")}
                aria-pressed={documentIndex === index}
                onClick={() => selectDocument(index)}
              >
                <span className="document-name">
                  <Icon name="file" size={16} /> {item.name}
                </span>
                <small>{item.description}</small>
                <span>
                  {item.chunks.length} chunks · Indexed · {item.updated}
                </span>
              </button>
            ))}
          </div>
        </Panel>
        <Panel
          title={document.name}
          hint="Source excerpts and indexing versions"
          action={
            <label className="version-picker">
              <span className="sr-only">Chunk version</span>
              <select
                className="select-control compact"
                value={version}
                aria-label="Chunk version"
                onChange={(event) => {
                  setVersion(Number(event.target.value));
                  setChunkIndex(0);
                }}
              >
                {Array.from({ length: document.versions }, (_, i) => document.versions - i).map(
                  (value) => (
                    <option value={value} key={value}>
                      Version {value} {value === document.versions ? "· active" : "· historical"}
                    </option>
                  ),
                )}
              </select>
            </label>
          }
        >
          {version !== document.versions ? (
            <div className="inline-notice">
              <Icon name="info" size={16} /> Historical sample snapshot · not used in live
              retrieval.
            </div>
          ) : null}
          <div className="chunk-cards">
            {chunks.map((text, index) => (
              <button
                type="button"
                key={index}
                aria-pressed={chunkIndex === index}
                onClick={() => setChunkIndex(index)}
                className={"chunk-entry " + (chunkIndex === index ? "active" : "")}
              >
                <div className="chunk-entry-head">
                  <span className="result-rank">{String(index + 1).padStart(2, "0")}</span>
                  <strong>Chunk {index + 1}</strong>
                  <span className="status-badge success">Embedded</span>
                </div>
                <p>{text}</p>
                <span className="text-hint">
                  Offset {index * 1_000}–{index * 1_000 + text.length}
                </span>
              </button>
            ))}
          </div>
          <div className="chunk-details">
            <h3>Selected chunk details</h3>
            <p>{activeChunk}</p>
            <div className="chunk-facts">
              <span>
                Version <strong>{version}</strong>
              </span>
              <span>
                Chunk{" "}
                <strong>
                  {chunkIndex + 1} / {chunks.length}
                </strong>
              </span>
              <span>
                Characters <strong>{activeChunk.length}</strong>
              </span>
            </div>
            <ScoreMeter label="Embedding available" score={1} variant="cyan" />
            <p className="text-hint">
              These version IDs, offsets and availability indicators are illustrative.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
