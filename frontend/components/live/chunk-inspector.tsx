"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Icon } from "@/components/icons";
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel } from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import type { ChunkVersion, PersistedChunk } from "@/lib/chunk-inspection-types";
import type { LiveDocument, LiveKnowledgeBase } from "@/lib/live-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

interface Props {
  initialKnowledgeBaseId?: string;
  initialDocumentId?: string;
}

function formattedDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown date"
    : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function PreviewText({ children }: { children: string }) {
  return <pre className="live-chunk-preview">{children}</pre>;
}

export function LiveChunkInspectorPage({ initialKnowledgeBaseId, initialDocumentId }: Props) {
  const notify = useDemoToast();
  const [preferredKnowledgeBase, setPreferredKnowledgeBase] = useState(
    initialKnowledgeBaseId ?? "",
  );
  const [preferredDocument, setPreferredDocument] = useState(initialDocumentId ?? "");
  const [versionChoice, setVersionChoice] = useState("active");
  const [preferredChunk, setPreferredChunk] = useState("");
  const [documentFilter, setDocumentFilter] = useState("");
  const [chunkFilter, setChunkFilter] = useState("");

  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const knowledgeBase =
    bases.items.find((item) => item.id === preferredKnowledgeBase) ?? bases.items[0] ?? null;

  const documentsPath = knowledgeBase
    ? `/api/workspace/knowledge-bases/${knowledgeBase.id}/documents`
    : null;
  const documents = useWorkspacePages<LiveDocument>(documentsPath);
  const document =
    documents.items.find((item) => item.id === preferredDocument) ?? documents.items[0] ?? null;

  const docPrefix =
    knowledgeBase && document
      ? `/api/workspace/knowledge-bases/${knowledgeBase.id}/documents/${document.id}`
      : null;
  const versions = useWorkspacePages<ChunkVersion>(docPrefix ? `${docPrefix}/versions` : null);

  const selectedVersion =
    versionChoice === "active"
      ? null
      : (versions.items.find((item) => `v:${item.version}` === versionChoice) ?? null);
  const chunksPath = docPrefix
    ? selectedVersion
      ? `${docPrefix}/chunks?version=${selectedVersion.version}`
      : `${docPrefix}/chunks`
    : null;
  const chunks = useWorkspacePages<PersistedChunk>(chunksPath);
  const selectedChunk =
    chunks.items.find((item) => item.id === preferredChunk) ?? chunks.items[0] ?? null;

  const visibleDocuments = useMemo(() => {
    const filter = documentFilter.trim().toLowerCase();
    return documents.items.filter((item) => item.filename.toLowerCase().includes(filter));
  }, [documents.items, documentFilter]);
  const visibleChunks = useMemo(() => {
    const filter = chunkFilter.trim().toLowerCase();
    return chunks.items.filter(
      (item) =>
        item.text.toLowerCase().includes(filter) ||
        String(item.index + 1) === filter ||
        item.id.toLowerCase().includes(filter),
    );
  }, [chunks.items, chunkFilter]);

  const activeVersion = document?.active_chunk_version ?? 0;
  const selectionIsHistorical = selectedVersion !== null && !selectedVersion.is_active;
  const loadedEmbedded = chunks.items.filter((item) => item.has_embeddings).length;
  const loadedWithoutEmbeddings = chunks.items.length - loadedEmbedded;

  function selectBase(id: string) {
    setPreferredKnowledgeBase(id);
    setPreferredDocument("");
    setPreferredChunk("");
    setVersionChoice("active");
    setDocumentFilter("");
    setChunkFilter("");
  }

  function selectDocument(id: string) {
    setPreferredDocument(id);
    setPreferredChunk("");
    setVersionChoice("active");
    setChunkFilter("");
  }

  function chooseVersion(value: string) {
    setVersionChoice(value);
    setPreferredChunk("");
    setChunkFilter("");
  }

  async function copyChunk(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      notify("Saved source text copied.");
    } catch {
      notify("Clipboard access is unavailable.");
    }
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE DOCUMENT INTELLIGENCE"
        title="Chunk inspector"
        description="Inspect actual indexed text, tokenizer-specific token counts, source offsets, embeddings and immutable processing history."
        badge="Live PostgreSQL data"
        action={
          <Link href="/knowledge-bases" className="button ghost compact">
            <Icon name="arrow-right" size={15} /> Manage documents
          </Link>
        }
      />

      <div className="inline-notice">
        <Icon name="shield" size={17} />
        Read-only inspection of your real Spurel database. Historical chunks are not visible to
        normal retrieval; the active index is shown separately.
      </div>

      <div className="live-inspector-grid">
        <Panel title="Source library" hint="Choose a knowledge base and a saved document">
          <label htmlFor="inspector-base" className="field-label">
            Knowledge base
          </label>
          {bases.loading ? (
            <LoadingState label="Loading knowledge bases" />
          ) : bases.error ? (
            <ErrorState description={bases.error} onRetry={bases.refresh} />
          ) : bases.items.length === 0 ? (
            <EmptyState
              icon="database"
              title="No knowledge bases"
              description="Create a knowledge base and upload a document to inspect real chunks."
              action={
                <Link href="/knowledge-bases" className="button primary">
                  Create a collection
                </Link>
              }
            />
          ) : (
            <>
              <select
                id="inspector-base"
                className="select-control"
                value={knowledgeBase?.id ?? ""}
                onChange={(event) => selectBase(event.target.value)}
              >
                {bases.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {bases.hasMore ? (
                <button
                  type="button"
                  className="button ghost compact live-load-more"
                  disabled={bases.loadingMore}
                  onClick={() => void bases.loadMore()}
                >
                  {bases.loadingMore ? "Loading…" : "Load more knowledge bases"}
                </button>
              ) : null}
              <div className="live-inspector-section-heading">
                <strong>Documents</strong>
                <button
                  type="button"
                  className="button ghost compact"
                  disabled={documents.loading}
                  onClick={documents.refresh}
                >
                  <Icon name="refresh" size={14} /> Refresh
                </button>
              </div>
              <label htmlFor="inspector-doc-search" className="sr-only">
                Filter loaded documents
              </label>
              <input
                id="inspector-doc-search"
                className="input-control"
                type="search"
                placeholder="Search loaded documents"
                value={documentFilter}
                onChange={(event) => setDocumentFilter(event.target.value)}
              />
              {documents.loading ? (
                <LoadingState label="Loading documents" />
              ) : documents.error ? (
                <ErrorState description={documents.error} onRetry={documents.refresh} />
              ) : documents.items.length === 0 ? (
                <EmptyState
                  icon="file"
                  title="No documents"
                  description="Upload a PDF, Markdown or text file in Knowledge Bases first."
                  action={
                    <Link href="/knowledge-bases" className="button ghost">
                      Upload documents
                    </Link>
                  }
                />
              ) : (
                <>
                  {visibleDocuments.length === 0 ? (
                    <p className="muted-panel-note">No loaded documents match your filter.</p>
                  ) : (
                    <div className="document-list live-inspector-documents">
                      {visibleDocuments.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          className={"document-item " + (item.id === document?.id ? "active" : "")}
                          aria-pressed={item.id === document?.id}
                          onClick={() => selectDocument(item.id)}
                        >
                          <span className="document-name">
                            <Icon name="file" size={16} /> {item.filename}
                          </span>
                          <small>{formattedDate(item.created_at)}</small>
                          <span>
                            {item.active_chunk_version
                              ? `Active index · v${item.active_chunk_version}`
                              : "Uploaded · not indexed"}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                  {documents.hasMore ? (
                    <button
                      type="button"
                      className="button ghost compact live-load-more"
                      disabled={documents.loadingMore}
                      onClick={() => void documents.loadMore()}
                    >
                      {documents.loadingMore ? "Loading…" : "Load more documents"}
                    </button>
                  ) : null}
                </>
              )}
            </>
          )}
        </Panel>

        <div className="live-inspector-main">
          {document ? (
            <>
              <Panel
                title={document.filename}
                hint="Versioned source inspection — no changes are made to stored documents"
                action={
                  <span className={"status-badge " + (activeVersion ? "success" : "warn")}>
                    {activeVersion ? `Active v${activeVersion}` : "Not indexed"}
                  </span>
                }
              >
                <div className="live-chunk-facts">
                  <span>
                    <strong>{activeVersion || "None"}</strong>
                    <small>Active version</small>
                  </span>
                  <span>
                    <strong>{versions.items.length}</strong>
                    <small>Loaded versions</small>
                  </span>
                  <span>
                    <strong>{chunks.items.length}</strong>
                    <small>Loaded chunks</small>
                  </span>
                  <span>
                    <strong>
                      {loadedEmbedded}/{chunks.items.length}
                    </strong>
                    <small>With embeddings</small>
                  </span>
                </div>
                <div className="live-version-controls">
                  <div>
                    <label className="field-label" htmlFor="inspector-version">
                      Chunk set to inspect
                    </label>
                    <select
                      id="inspector-version"
                      className="select-control"
                      value={selectedVersion ? versionChoice : "active"}
                      onChange={(event) => chooseVersion(event.target.value)}
                    >
                      <option value="active">
                        {activeVersion
                          ? `Active version ${activeVersion} · live retrieval`
                          : "Current active index · none"}
                      </option>
                      {versions.items.map((item) => (
                        <option key={item.version} value={`v:${item.version}`}>
                          Version {item.version} · {item.status}
                          {item.is_active ? " · current" : " · not active"}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    className="button ghost compact"
                    disabled={versions.loading}
                    onClick={versions.refresh}
                  >
                    <Icon name="refresh" size={14} /> Refresh versions
                  </button>
                </div>
                {versions.loading ? <LoadingState label="Loading version history" /> : null}
                {versions.error ? (
                  <ErrorState description={versions.error} onRetry={versions.refresh} />
                ) : null}
                {versions.hasMore ? (
                  <button
                    type="button"
                    className="button ghost compact live-load-more"
                    disabled={versions.loadingMore}
                    onClick={() => void versions.loadMore()}
                  >
                    {versions.loadingMore ? "Loading…" : "Load older versions"}
                  </button>
                ) : null}
                {selectionIsHistorical ? (
                  <div className="inline-notice">
                    <Icon name="clock" size={16} />
                    Historical version {selectedVersion?.version} is read-only. These chunks are not
                    used for normal vector, keyword or hybrid retrieval.
                  </div>
                ) : selectedVersion && selectedVersion.status !== "ready" ? (
                  <div className="inline-notice">
                    <Icon name="info" size={16} />
                    Selected version is {selectedVersion.status}. The current active version remains
                    separate until an index is published.
                  </div>
                ) : null}
                {activeVersion === 0 && !selectedVersion ? (
                  <div className="inline-notice">
                    <Icon name="info" size={16} />
                    This document has not published an active chunk set. You can inspect any saved
                    processing attempts above or process it from Knowledge Bases.
                  </div>
                ) : null}
                <div className="live-inspector-section-heading">
                  <strong>Stored chunks</strong>
                  <button
                    type="button"
                    className="button ghost compact"
                    disabled={chunks.loading}
                    onClick={chunks.refresh}
                  >
                    <Icon name="refresh" size={14} /> Refresh chunks
                  </button>
                </div>
                {chunks.items.length ? (
                  <>
                    <label htmlFor="inspector-chunk-filter" className="field-label">
                      Find text or index in loaded chunks
                    </label>
                    <input
                      id="inspector-chunk-filter"
                      className="input-control"
                      type="search"
                      value={chunkFilter}
                      placeholder="Filter loaded excerpts"
                      onChange={(event) => setChunkFilter(event.target.value)}
                    />
                  </>
                ) : null}
                {chunks.loading ? (
                  <LoadingState label="Reading stored chunks" />
                ) : chunks.error ? (
                  <ErrorState description={chunks.error} onRetry={chunks.refresh} />
                ) : chunks.items.length === 0 ? (
                  <EmptyState
                    title="No chunks in this selection"
                    icon="layers"
                    description="Upload and process a document to create searchable chunks, or select a different saved version."
                    action={
                      <Link href="/knowledge-bases" className="button ghost compact">
                        Open documents
                      </Link>
                    }
                  />
                ) : visibleChunks.length === 0 ? (
                  <EmptyState
                    title="No loaded chunks match"
                    description="Clear the text filter or load another page of chunks."
                    action={
                      <button
                        type="button"
                        className="button ghost compact"
                        onClick={() => setChunkFilter("")}
                      >
                        Clear filter
                      </button>
                    }
                  />
                ) : (
                  <div className="chunk-cards live-inspector-chunks">
                    {visibleChunks.map((item) => (
                      <button
                        type="button"
                        key={item.id}
                        className={"chunk-entry " + (selectedChunk?.id === item.id ? "active" : "")}
                        aria-pressed={selectedChunk?.id === item.id}
                        onClick={() => setPreferredChunk(item.id)}
                      >
                        <div className="chunk-entry-head">
                          <span className="result-rank">
                            {String(item.index + 1).padStart(2, "0")}
                          </span>
                          <strong>Chunk {item.index + 1}</strong>
                          <span
                            className={"status-badge " + (item.has_embeddings ? "success" : "warn")}
                          >
                            {item.has_embeddings
                              ? `${item.embedding_count} embedding${item.embedding_count === 1 ? "" : "s"}`
                              : "No embeddings"}
                          </span>
                        </div>
                        <p>{item.text}</p>
                        <small className="text-hint">
                          Source offsets {item.start_offset}–{item.end_offset}
                          {item.token_count !== null && item.token_count !== undefined
                            ? ` · ${item.token_count} tokens (${item.tokenizer_encoding})`
                            : ""}
                        </small>
                      </button>
                    ))}
                  </div>
                )}
                {chunks.hasMore ? (
                  <button
                    type="button"
                    className="button ghost live-load-more"
                    disabled={chunks.loadingMore}
                    onClick={() => void chunks.loadMore()}
                  >
                    {chunks.loadingMore ? "Loading…" : "Load more chunks"}
                  </button>
                ) : null}
                <p className="muted-panel-note">
                  {chunks.items.length} chunk{chunks.items.length === 1 ? "" : "s"} loaded;{" "}
                  {loadedEmbedded} have embeddings and {loadedWithoutEmbeddings} do not. Counts
                  reflect loaded pages, not the entire index.
                </p>
              </Panel>
              {selectedChunk ? (
                <Panel
                  title={`Source excerpt · Chunk ${selectedChunk.index + 1}`}
                  hint="Full persisted text and exact source offsets"
                  action={
                    <button
                      type="button"
                      className="button ghost compact"
                      onClick={() => void copyChunk(selectedChunk.text)}
                    >
                      <Icon name="copy" size={14} /> Copy exact text
                    </button>
                  }
                >
                  <PreviewText>{selectedChunk.text}</PreviewText>
                  <div className="live-chunk-details">
                    <span>
                      Chunk ID <strong>{selectedChunk.id}</strong>
                    </span>
                    <span>
                      Document ID <strong>{selectedChunk.document_id}</strong>
                    </span>
                    <span>
                      Source start <strong>{selectedChunk.start_offset}</strong>
                    </span>
                    <span>
                      Source end <strong>{selectedChunk.end_offset}</strong>
                    </span>
                    <span>
                      Excerpt characters <strong>{selectedChunk.text.length}</strong>
                    </span>
                    <span>
                      Token count
                      <strong>
                        {selectedChunk.token_count === undefined || selectedChunk.token_count === null
                          ? "Unavailable"
                          : selectedChunk.token_count}
                      </strong>
                    </span>
                    <span>
                      Tokenizer encoding
                      <strong>{selectedChunk.tokenizer_encoding ?? "Unavailable"}</strong>
                    </span>
                    <span>
                      Embedding records <strong>{selectedChunk.embedding_count}</strong>
                    </span>
                  </div>
                  <p className="text-hint">
                    Token counts are calculated for the currently configured embedding-model
                    tokenizer, including historical chunks. If the model changes, an older
                    version&apos;s displayed count is recalculated, not its original tokenizer metadata.
                  </p>
                </Panel>
              ) : null}
            </>
          ) : (
            <Panel title="Chunk inspection">
              {documents.loading || bases.loading ? (
                <LoadingState label="Loading your source library" />
              ) : (
                <EmptyState
                  title="Select a document"
                  description="Choose an uploaded document from the source library to inspect its active index and historical versions."
                  icon="layers"
                />
              )}
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
