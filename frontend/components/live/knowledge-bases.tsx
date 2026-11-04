"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/icons";
import {
  DEFAULT_CHUNKING,
  TOKEN_CHUNKING,
  isLegacyChunking,
  parseChunkingOptions,
  type ChunkStrategy,
} from "@/lib/chunking-options";
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel } from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import { liveError, isPage, workspaceFetch } from "@/lib/live-client";
import type { LiveDocument, LiveKnowledgeBase, Page, ProcessedDocument } from "@/lib/live-types";

const PAGE_SIZE = 50;

function documentDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown date"
    : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function readableSize(bytes: number): string {
  return bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function appendDistinct<T extends { id: string }>(original: T[], incoming: T[]): T[] {
  const ids = new Set(original.map((item) => item.id));
  return [...original, ...incoming.filter((item) => !ids.has(item.id))];
}

export function LiveKnowledgeBasesPage() {
  const router = useRouter();
  const notify = useDemoToast();
  const [bases, setBases] = useState<LiveKnowledgeBase[]>([]);
  const [preferredId, setPreferredId] = useState<string | null>(null);
  const selectedId = bases.some((base) => base.id === preferredId)
    ? preferredId
    : (bases[0]?.id ?? null);
  const selected = bases.find((base) => base.id === selectedId) ?? null;

  const [basesLoading, setBasesLoading] = useState(true);
  const [basesError, setBasesError] = useState("");
  const [basesMore, setBasesMore] = useState(false);
  const [basesBusy, setBasesBusy] = useState(false);
  const [documents, setDocuments] = useState<LiveDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsMore, setDocumentsMore] = useState(false);
  const [documentsError, setDocumentsError] = useState("");
  const [documentsBusy, setDocumentsBusy] = useState(false);
  const requestSequence = useRef(0);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [creatingBusy, setCreatingBusy] = useState(false);
  const [submittingError, setSubmittingError] = useState("");
  const [uploadBusy, setUploadBusy] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [chunkStrategy, setChunkStrategy] = useState<ChunkStrategy>("characters");
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNKING.chunk_size);
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNKING.overlap);

  const [actionError, setActionError] = useState("");
  const [search, setSearch] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);

  const visibleBases = useMemo(
    () => bases.filter((base) => base.name.toLowerCase().includes(search.toLowerCase().trim())),
    [bases, search],
  );

  const loadBases = useCallback(async (offset: number, replace = false) => {
    if (offset === 0) setBasesLoading(true);
    else setBasesBusy(true);
    setBasesError("");
    try {
      const page = await workspaceFetch<Page<LiveKnowledgeBase>>(
        `/api/workspace/knowledge-bases?offset=${offset}`,
      );
      if (!isPage<LiveKnowledgeBase>(page)) throw new Error("Unexpected knowledge-base response.");
      setBases((current) => (replace ? page.items : appendDistinct(current, page.items)));
      setBasesMore(page.items.length === PAGE_SIZE);
    } catch (cause) {
      setBasesError(liveError(cause));
    } finally {
      setBasesLoading(false);
      setBasesBusy(false);
    }
  }, []);

  const loadDocuments = useCallback(async (kbId: string, offset: number, replace = false) => {
    const token = ++requestSequence.current;
    if (offset === 0) setDocumentsLoading(true);
    else setDocumentsBusy(true);
    setDocumentsError("");
    try {
      const page = await workspaceFetch<Page<LiveDocument>>(
        `/api/workspace/knowledge-bases/${kbId}/documents?offset=${offset}`,
      );
      if (!isPage<LiveDocument>(page)) throw new Error("Unexpected document response.");
      if (token !== requestSequence.current) return;
      setDocuments((current) => (replace ? page.items : appendDistinct(current, page.items)));
      setDocumentsMore(page.items.length === PAGE_SIZE);
    } catch (cause) {
      if (token === requestSequence.current) setDocumentsError(liveError(cause));
    } finally {
      if (token === requestSequence.current) {
        setDocumentsLoading(false);
        setDocumentsBusy(false);
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) return loadBases(0, true);
    });
    return () => {
      cancelled = true;
    };
  }, [loadBases]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled && selectedId) return loadDocuments(selectedId, 0, true);
    });
    return () => {
      cancelled = true;
      requestSequence.current += 1;
    };
  }, [selectedId, loadDocuments]);

  async function createBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creatingBusy || !newName.trim()) return;
    setCreatingBusy(true);
    setSubmittingError("");
    try {
      const base = await workspaceFetch<LiveKnowledgeBase>("/api/workspace/knowledge-bases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      });
      setBases((current) => [base, ...current.filter((item) => item.id !== base.id)]);
      setDocuments([]);
      setDocumentsMore(false);
      setPreferredId(base.id);
      setNewName("");
      setSearch("");
      setCreating(false);
      notify("Knowledge base created in PostgreSQL.");
    } catch (cause) {
      setSubmittingError(liveError(cause));
    } finally {
      setCreatingBusy(false);
    }
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId || uploadBusy) return;
    const input = event.currentTarget.elements.namedItem("document") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      setActionError("Choose a PDF, Markdown or text file.");
      return;
    }
    if (file.size === 0 || file.size > 25 * 1024 * 1024) {
      setActionError("Files must be nonempty and no larger than 25 MB.");
      return;
    }
    setUploadBusy(true);
    setActionError("");
    try {
      const form = new FormData();
      form.set("file", file);
      const result = await workspaceFetch<LiveDocument>(
        `/api/workspace/knowledge-bases/${selectedId}/documents`,
        { method: "POST", body: form },
      );
      setDocuments((current) => [result, ...current.filter((item) => item.id !== result.id)]);
      input.value = "";
      notify("Document uploaded to Spurel. Process it to create searchable chunks.");
    } catch (cause) {
      setActionError(liveError(cause));
    } finally {
      setUploadBusy(false);
    }
  }

  async function processDocument(document: LiveDocument) {
    if (!selectedId || processingId) return;
    const options = parseChunkingOptions({
      strategy: chunkStrategy,
      chunk_size: chunkSize,
      overlap: chunkOverlap,
    });
    if (!options) {
      setActionError("Choose a valid chunk size and an overlap smaller than the size.");
      return;
    }
    const legacy = isLegacyChunking(options);
    if (
      !legacy &&
      !window.confirm(
        `Process ${document.filename} with ${chunkStrategy} chunking (${options.chunk_size} ${chunkStrategy === "tokens" ? "tokens" : "characters"} per chunk, ${options.overlap} overlap)? Embeddings may incur OpenAI charges. Existing active versions remain available until processing succeeds.`,
      )
    )
      return;
    setProcessingId(document.id);
    setActionError("");
    try {
      const result = await workspaceFetch<ProcessedDocument>(
        `/api/workspace/knowledge-bases/${selectedId}/documents/${document.id}/process`,
        legacy
          ? { method: "POST" }
          : {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(options),
            },
      );
      setDocuments((current) =>
        current.map((item) =>
          item.id === document.id ? { ...item, active_chunk_version: result.chunk_version } : item,
        ),
      );
      notify(`Indexed ${result.chunk_count} chunks in version ${result.chunk_version}.`);
    } catch (cause) {
      setActionError(
        liveError(cause) +
          " Processing requires a valid OpenAI embedding key and configured model.",
      );
    } finally {
      setProcessingId(null);
    }
  }

  async function logout() {
    setLoggingOut(true);
    try {
      await workspaceFetch<{ authenticated: boolean }>("/api/operator/logout", { method: "POST" });
      router.replace("/operator/login");
      router.refresh();
    } catch (cause) {
      setBasesError(liveError(cause));
    } finally {
      setLoggingOut(false);
    }
  }

  const indexed = documents.filter((item) => item.active_chunk_version > 0).length;

  return (
    <div className="screen">
      <PageHeading
        eyebrow="LIVE POSTGRESQL WORKSPACE"
        title="Knowledge bases"
        description="Manage real source collections, upload documents, and trigger indexing."
        badge="Live backend"
        action={
          <>
            <button
              type="button"
              className="button ghost"
              onClick={() => void logout()}
              disabled={loggingOut}
            >
              <Icon name="shield" size={15} /> Sign out
            </button>
            <button type="button" className="button primary" onClick={() => setCreating(true)}>
              <Icon name="plus" size={15} /> New knowledge base
            </button>
          </>
        }
      />

      <div className="inline-notice">
        <Icon name="check" size={17} />
        This screen shows actual FastAPI and PostgreSQL data. Retrieval, trace history, evaluations
        and RAG answers use live backend integrations; the Overview summarizes real persisted
        records from this local workspace.
      </div>

      <Panel
        title="Source collections"
        hint="Real knowledge-base records · showing loaded pages"
        action={
          <button
            type="button"
            className="button ghost compact"
            disabled={basesLoading || basesBusy}
            onClick={() => void loadBases(0, true)}
          >
            <Icon name="refresh" size={14} /> Refresh
          </button>
        }
      >
        <label className="field-label" htmlFor="live-kb-search">
          Filter collections
        </label>
        <input
          id="live-kb-search"
          type="search"
          className="input-control"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search loaded knowledge bases..."
        />
        {basesError ? (
          <ErrorState description={basesError} onRetry={() => void loadBases(0, true)} />
        ) : null}
        {basesLoading ? (
          <LoadingState label="Loading knowledge bases" />
        ) : bases.length === 0 && !basesError ? (
          <EmptyState
            title="No knowledge bases yet"
            description="Create your first collection to organize documents and indexed evidence."
            icon="database"
            action={
              <button type="button" className="button primary" onClick={() => setCreating(true)}>
                Create knowledge base
              </button>
            }
          />
        ) : (
          <>
            {visibleBases.length === 0 && search ? (
              <p className="muted-panel-note">No loaded collections match your search.</p>
            ) : (
              <div className="kb-grid live-grid">
                {visibleBases.map((base) => (
                  <button
                    key={base.id}
                    type="button"
                    aria-pressed={base.id === selectedId}
                    className={"knowledge-card " + (base.id === selectedId ? "selected" : "")}
                    onClick={() => {
                      setDocuments([]);
                      setDocumentsMore(false);
                      setActionError("");
                      setPreferredId(base.id);
                    }}
                  >
                    <span className="kb-card-icon">
                      <Icon name="database" size={22} />
                    </span>
                    <strong>{base.name}</strong>
                    <p>Knowledge base created {documentDate(base.created_at)}.</p>
                    <span className="kb-category">Live collection · {base.id.slice(0, 8)}</span>
                    <span className="kb-card-footer">Select to view documents</span>
                  </button>
                ))}
              </div>
            )}
            {basesMore ? (
              <button
                type="button"
                className="button ghost live-load-more"
                disabled={basesBusy}
                onClick={() => void loadBases(bases.length)}
              >
                {basesBusy ? "Loading…" : "Load more collections"}
              </button>
            ) : null}
          </>
        )}
      </Panel>

      {selected ? (
        <Panel
          title={selected.name + " · Documents"}
          hint="Live upload, indexed versions and processing"
          action={
            <button
              type="button"
              className="button ghost compact"
              disabled={documentsLoading || documentsBusy}
              onClick={() => void loadDocuments(selected.id, 0, true)}
            >
              <Icon name="refresh" size={14} /> Refresh docs
            </button>
          }
        >
          <div className="live-summary-grid">
            <span>
              <strong>{documents.length}</strong>
              <small>Loaded documents</small>
            </span>
            <span>
              <strong>{indexed}</strong>
              <small>Indexed in loaded page</small>
            </span>
            <span>
              <strong>{documents.length - indexed}</strong>
              <small>Not indexed yet</small>
            </span>
          </div>
          <form className="live-upload-form" onSubmit={uploadFile}>
            <div>
              <label htmlFor="live-upload" className="field-label">
                Upload PDF, Markdown or text
              </label>
              <input
                id="live-upload"
                className="input-control"
                name="document"
                type="file"
                accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
                required
              />
              <p className="text-hint">
                Up to 25 MB. Upload stores the file; processing creates searchable embeddings.
              </p>
            </div>
            <button type="submit" className="button primary" disabled={uploadBusy}>
              <Icon name="upload" size={15} /> {uploadBusy ? "Uploading…" : "Upload document"}
            </button>
          </form>
          <div className="live-chunking-settings">
            <div>
              <strong>Chunking settings for the next processing run</strong>
              <p className="text-hint">
                Character and model-token methods remain unchanged. Add recursive, Markdown-heading
                or sentence-aware splitting when you want to preserve document structure. Nothing is
                reprocessed until you click Process or Reprocess.
              </p>
            </div>
            <div className="live-chunking-controls">
              <div>
                <label htmlFor="chunk-strategy" className="field-label">
                  Chunking method
                </label>
                <select
                  id="chunk-strategy"
                  className="select-control"
                  value={chunkStrategy}
                  onChange={(event) => {
                    const strategy = event.target.value as ChunkStrategy;
                    const defaults = strategy === "tokens" ? TOKEN_CHUNKING : DEFAULT_CHUNKING;
                    setChunkStrategy(strategy);
                    setChunkSize(defaults.chunk_size);
                    setChunkOverlap(defaults.overlap);
                  }}
                >
                  <option value="characters">Characters · existing default</option>
                  <option value="tokens">Model tokens · opt-in</option>
                  <option value="recursive">Recursive · paragraphs and lines</option>
                  <option value="markdown">Markdown · heading-aware sections</option>
                  <option value="sentences">Sentences · natural boundaries</option>
                </select>
              </div>
              <div>
                <label htmlFor="chunk-size" className="field-label">
                  Chunk size ({chunkStrategy === "tokens" ? "tokens" : "characters"})
                </label>
                <input
                  id="chunk-size"
                  className="input-control"
                  type="number"
                  min={1}
                  max={chunkStrategy === "tokens" ? 2000 : 20000}
                  value={chunkSize}
                  onChange={(event) => setChunkSize(Number(event.target.value))}
                />
              </div>
              <div>
                <label htmlFor="chunk-overlap" className="field-label">
                  Overlap ({chunkStrategy === "tokens" ? "tokens" : "characters"})
                </label>
                <input
                  id="chunk-overlap"
                  className="input-control"
                  type="number"
                  min={0}
                  max={Math.max(0, chunkSize - 1)}
                  value={chunkOverlap}
                  onChange={(event) => setChunkOverlap(Number(event.target.value))}
                />
              </div>
            </div>
            {chunkStrategy === "tokens" ? (
              <p className="text-hint">
                Token counts use the tokenizer for the configured embedding model. A
                20,000-character source-span safety cap also applies. Reprocessing creates a new
                staged version when chunk boundaries change; older versions remain inspectable.
              </p>
            ) : null}
            {chunkStrategy === "recursive" ||
            chunkStrategy === "markdown" ||
            chunkStrategy === "sentences" ? (
              <p className="text-hint">
                {chunkStrategy === "recursive"
                  ? "Prefer paragraph, sentence, then line/word breaks; long spans fall back to character windows."
                  : chunkStrategy === "markdown"
                    ? "Prefer Markdown headings as section boundaries, ignoring heading-like text in fenced code."
                    : "Prefer complete sentences; oversized sentences fall back to line or word breaks."}{" "}
                Size and overlap are measured in characters. Overlap may be reduced to keep
                boundaries intact; previous index versions remain available.
              </p>
            ) : null}
          </div>
          {actionError ? (
            <div className="inline-notice live-error" role="alert">
              {actionError}
            </div>
          ) : null}
          {documentsError ? (
            <ErrorState
              description={documentsError}
              onRetry={() => void loadDocuments(selected.id, 0, true)}
            />
          ) : null}
          {documentsLoading ? (
            <LoadingState label="Loading saved documents" />
          ) : documents.length === 0 && !documentsError ? (
            <EmptyState
              title="No documents uploaded"
              icon="file"
              description="Upload a supported file to start indexing this knowledge base."
            />
          ) : (
            <div className="live-doc-list">
              {documents.map((document) => (
                <div className="live-doc-item" key={document.id}>
                  <span className="recent-icon">
                    <Icon name="file" size={18} />
                  </span>
                  <div className="live-doc-info">
                    <strong title={document.filename}>{document.filename}</strong>
                    <small>
                      {readableSize(document.size_bytes)} · {documentDate(document.created_at)}
                    </small>
                    <span
                      className={
                        "status-badge " + (document.active_chunk_version ? "success" : "warn")
                      }
                    >
                      {document.active_chunk_version
                        ? `Indexed · version ${document.active_chunk_version}`
                        : "Uploaded · not indexed"}
                    </span>
                  </div>
                  <Link
                    href={`/chunks?kb=${selectedId}&doc=${document.id}`}
                    className="button ghost compact"
                    aria-label={`Inspect chunks of ${document.filename}`}
                  >
                    <Icon name="layers" size={14} /> Inspect chunks
                  </Link>
                  <button
                    type="button"
                    className="button ghost compact"
                    disabled={Boolean(processingId)}
                    onClick={() => void processDocument(document)}
                  >
                    <Icon name="zap" size={14} />
                    {processingId === document.id
                      ? "Processing…"
                      : document.active_chunk_version
                        ? "Reprocess"
                        : "Process"}
                  </button>
                </div>
              ))}
            </div>
          )}
          {documentsMore ? (
            <button
              type="button"
              className="button ghost live-load-more"
              disabled={documentsBusy}
              onClick={() => void loadDocuments(selected.id, documents.length)}
            >
              {documentsBusy ? "Loading…" : "Load more documents"}
            </button>
          ) : null}
          <div className="retrieval-source-link">
            <Link href={`/retrieval?kb=${selected.id}`} className="button ghost compact">
              <Icon name="search" size={15} /> Search this knowledge base
            </Link>
            <span className="text-hint">
              Keyword search works without a query-time embedding call.
            </span>
          </div>
          <p className="muted-panel-note">
            Processing requires <code>OPENAI_API_KEY</code> in your server environment. Inspect the
            active index and older versions in the Chunk Inspector.
          </p>
        </Panel>
      ) : null}

      {creating ? (
        <div className="dialog-backdrop" onMouseDown={() => !creatingBusy && setCreating(false)}>
          <section
            className="simple-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="New knowledge base"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="dialog-heading">
              <div>
                <h2>Create knowledge base</h2>
                <p>This collection will be saved in your Spurel PostgreSQL database.</p>
              </div>
              <button
                type="button"
                className="icon-button"
                aria-label="Close dialog"
                onClick={() => setCreating(false)}
                disabled={creatingBusy}
              >
                <Icon name="x" size={16} />
              </button>
            </div>
            <form onSubmit={createBase}>
              <label className="field-label" htmlFor="new-live-kb-name">
                Knowledge-base name
              </label>
              <input
                id="new-live-kb-name"
                autoFocus
                className="input-control"
                maxLength={120}
                required
                placeholder="e.g. Product engineering"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
              />
              {submittingError ? (
                <p className="operator-error" role="alert">
                  {submittingError}
                </p>
              ) : null}
              <div className="dialog-actions">
                <button
                  type="button"
                  className="button ghost"
                  disabled={creatingBusy}
                  onClick={() => setCreating(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={creatingBusy || !newName.trim()}
                >
                  {creatingBusy ? "Creating…" : "Create collection"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
