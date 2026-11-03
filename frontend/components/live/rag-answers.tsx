"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { Icon } from "@/components/icons";
import { EmptyState, ErrorState, LoadingState, PageHeading, Panel } from "@/components/ui";
import { useDemoToast } from "@/components/workbench-shell";
import { liveError, workspaceFetch } from "@/lib/live-client";
import type { LiveKnowledgeBase } from "@/lib/live-types";
import {
  isRagAnswerResponse,
  parseRagAnswerRequest,
  type RagAnswerRequest,
  type RagAnswerResponse,
  type RagSource,
} from "@/lib/rag-types";
import { useWorkspacePages } from "@/lib/use-workspace-pages";

interface CompletedAnswer {
  knowledgeBaseId: string;
  request: RagAnswerRequest;
  response: RagAnswerResponse;
}

interface Props {
  initialKnowledgeBaseId?: string;
}

function answerWithNavigableCitations(
  answer: string,
  sources: RagSource[],
  selectedLabel: string,
  selectSource: (label: string) => void,
): ReactNode[] {
  const labels = new Set(sources.map((source) => source.label));
  return answer.split(/(\[S\d+\])/g).map((part, index) => {
    const label = part.startsWith("[") && part.endsWith("]") ? part.slice(1, -1) : "";
    if (labels.has(label)) {
      return (
        <button
          key={index}
          type="button"
          aria-label={`Inspect source ${label}`}
          aria-pressed={selectedLabel === label}
          className={
            "citation-chip rag-inline-citation " + (selectedLabel === label ? "selected" : "")
          }
          onClick={() => selectSource(label)}
        >
          {part}
        </button>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

export function LiveRagAnswersPage({ initialKnowledgeBaseId }: Props) {
  const notify = useDemoToast();
  const bases = useWorkspacePages<LiveKnowledgeBase>("/api/workspace/knowledge-bases");
  const [preferredBaseId, setPreferredBaseId] = useState(initialKnowledgeBaseId ?? "");
  const base = bases.items.find((item) => item.id === preferredBaseId) ?? bases.items[0] ?? null;
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(8);
  const [candidateK, setCandidateK] = useState(50);
  const [rrfK, setRrfK] = useState(60);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState<CompletedAnswer | null>(null);
  const [selectedLabel, setSelectedLabel] = useState("");
  const requestSequence = useRef(0);

  const current = completed && completed.knowledgeBaseId === base?.id ? completed : null;
  const answer = current?.response ?? null;
  const sources = answer?.sources ?? [];
  const selectedSource =
    sources.find((source) => source.label === selectedLabel) ?? sources[0] ?? null;
  const isStale = Boolean(
    current &&
    (question.trim() !== current.request.query ||
      topK !== current.request.top_k ||
      candidateK !== current.request.candidate_k ||
      rrfK !== current.request.rrf_k),
  );
  const request = parseRagAnswerRequest({
    query: question,
    top_k: topK,
    candidate_k: candidateK,
    rrf_k: rrfK,
  });

  function changeBase(value: string) {
    requestSequence.current += 1;
    setPreferredBaseId(value);
    setCompleted(null);
    setSelectedLabel("");
    setError("");
    setRunning(false);
  }

  function changeTopK(value: number) {
    const next = Math.max(1, Math.min(20, value));
    setTopK(next);
    setCandidateK((previous) => Math.max(previous, next));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!base || !request || running) return;

    if (
      !window.confirm(
        "This request runs hybrid retrieval and may call OpenAI for query embeddings and answer generation. Provider charges may apply. Generate this live answer?",
      )
    )
      return;

    const sequence = ++requestSequence.current;
    const knowledgeBaseId = base.id;
    setRunning(true);
    setError("");
    setCompleted(null);
    setSelectedLabel("");

    try {
      const data = await workspaceFetch<RagAnswerResponse>(
        `/api/workspace/knowledge-bases/${knowledgeBaseId}/rag/answer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        },
      );
      if (!isRagAnswerResponse(data)) {
        throw new Error("The RAG backend returned an invalid evidence response.");
      }
      if (requestSequence.current !== sequence) return;
      setCompleted({ knowledgeBaseId, request, response: data });
      setSelectedLabel(data.sources[0]?.label ?? "");
      notify(
        data.retrieved_chunk_count === 0
          ? "Live retrieval found no usable context; no answer-generation call was needed."
          : "Live RAG answer returned with saved retrieval trace.",
      );
    } catch (cause) {
      if (requestSequence.current === sequence) setError(liveError(cause));
    } finally {
      if (requestSequence.current === sequence) setRunning(false);
    }
  }

  async function copyAnswer() {
    if (!answer) return;
    try {
      await navigator.clipboard.writeText(answer.answer);
      notify("Generated answer copied.");
    } catch {
      notify("Clipboard access is unavailable in this browser.");
    }
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="REAL RETRIEVAL · REAL EVIDENCE"
        title="RAG answers"
        description="Ask an indexed knowledge base, inspect generated answers and follow their exact saved source excerpts."
        badge="Live FastAPI RAG"
        action={
          <Link className="button ghost compact" href="/knowledge-bases">
            <Icon name="database" size={15} /> Knowledge bases
          </Link>
        }
      />
      <div className="inline-notice">
        <Icon name="shield" size={16} />
        Generation is explicit and may use paid OpenAI embedding and text-generation calls. No model
        is called when loading the page or editing the form. Source labels are model attribution,
        not independently verified claim citations.
      </div>

      <Panel
        title="Ask your knowledge base"
        hint="Uses real indexed chunks and hybrid retrieval (vector + PostgreSQL full-text, fused by RRF)"
      >
        {bases.loading ? (
          <LoadingState label="Loading knowledge bases" />
        ) : bases.error ? (
          <ErrorState description={bases.error} onRetry={bases.refresh} />
        ) : !base ? (
          <EmptyState
            icon="database"
            title="No knowledge bases yet"
            description="Create a knowledge base and index at least one document to get grounded answers."
            action={
              <Link className="button ghost compact" href="/knowledge-bases">
                Manage sources
              </Link>
            }
          />
        ) : (
          <form onSubmit={(event) => void submit(event)}>
            <div className="rag-live-knowledge-base">
              <div>
                <label className="field-label" htmlFor="rag-knowledge-base">
                  Knowledge base
                </label>
                <select
                  id="rag-knowledge-base"
                  className="select-control"
                  value={base.id}
                  onChange={(event) => changeBase(event.target.value)}
                >
                  {bases.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </div>
              <Link className="button ghost compact" href={`/retrieval?kb=${base.id}`}>
                <Icon name="search" size={15} /> Inspect retrieval first
              </Link>
            </div>
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

            <label className="field-label" htmlFor="rag-question">
              Question
            </label>
            <textarea
              id="rag-question"
              className="textarea-control"
              rows={3}
              maxLength={8000}
              value={question}
              placeholder="Ask a question about information in your indexed documents"
              onChange={(event) => setQuestion(event.target.value)}
              required
            />

            <div className="rag-live-config">
              <div>
                <label className="field-label" htmlFor="rag-top-k">
                  Top K · final context chunks
                </label>
                <input
                  id="rag-top-k"
                  className="input-control"
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(event) => changeTopK(Number(event.target.value))}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="rag-candidate-k">
                  Candidate K · source pool
                </label>
                <input
                  id="rag-candidate-k"
                  className="input-control"
                  type="number"
                  min={topK}
                  max={100}
                  value={candidateK}
                  onChange={(event) => setCandidateK(Number(event.target.value))}
                />
              </div>
              <div>
                <label className="field-label" htmlFor="rag-rrf-k">
                  RRF K · fusion constant
                </label>
                <input
                  id="rag-rrf-k"
                  className="input-control"
                  type="number"
                  min={1}
                  max={1000}
                  value={rrfK}
                  onChange={(event) => setRrfK(Number(event.target.value))}
                />
              </div>
            </div>

            <div className="rag-actions">
              <span className="text-hint">
                Requires configured OpenAI embeddings and generation. Only previously indexed
                documents can be used as context.
              </span>
              <button type="submit" className="button primary" disabled={!request || running}>
                <Icon name="sparkles" size={15} />
                {running ? "Generating…" : "Generate live answer"}
              </button>
            </div>
            {running ? (
              <p className="muted-panel-note" role="status">
                Retrieving and generating against the selected knowledge base. This may take time;
                the request is not streaming.
              </p>
            ) : null}
          </form>
        )}
      </Panel>

      {error ? <ErrorState title="Live RAG request failed" description={error} /> : null}

      {answer && base ? (
        <>
          {isStale ? (
            <div className="inline-notice" role="status">
              <Icon name="info" size={16} />
              You changed the question or retrieval settings. The answer below belongs to the
              previous submitted request.
            </div>
          ) : null}
          <div className="rag-live-summary">
            <span>
              <small>Retrieved chunks</small>
              <strong>{answer.retrieved_chunk_count}</strong>
            </span>
            <span>
              <small>Context excerpts</small>
              <strong>{sources.length}</strong>
            </span>
            <span>
              <small>Generation provider</small>
              <strong>{answer.generation_provider ?? "Skipped · no context"}</strong>
            </span>
            <span>
              <small>Generation model</small>
              <strong>{answer.generation_model ?? "Not used"}</strong>
            </span>
          </div>

          <div className="results-grid">
            <Panel
              title="Live answer"
              hint={`Question: ${current?.request.query ?? ""}`}
              action={
                <button
                  type="button"
                  className="button ghost compact"
                  onClick={() => void copyAnswer()}
                >
                  <Icon name="copy" size={15} /> Copy answer
                </button>
              }
            >
              {answer.retrieved_chunk_count === 0 ? (
                <div className="inline-notice">
                  <Icon name="info" size={16} />
                  No matching indexed evidence was found, so the backend skipped text generation.
                  Try another question or index relevant documents.
                </div>
              ) : null}
              <div className="answer-message">
                <span className="answer-spark">
                  <Icon name="sparkles" size={20} />
                </span>
                <p className="rag-live-answer-text">
                  {answerWithNavigableCitations(
                    answer.answer,
                    sources,
                    selectedSource?.label ?? "",
                    setSelectedLabel,
                  )}
                </p>
              </div>
              <div className="rag-live-answer-actions">
                <Link
                  className="button ghost compact"
                  href={`/traces?kb=${base.id}&trace=${answer.trace_id}`}
                >
                  <Icon name="clock" size={15} /> Inspect saved retrieval trace
                </Link>
              </div>
              <p className="text-hint">
                Trace ID · {answer.trace_id}. Text is displayed as plain text; the appearance of a
                [S1] label alone does not prove that its claim is supported.
              </p>
            </Panel>

            <Panel
              title="Source evidence"
              hint="Exact excerpts passed to the generation model, not fabricated citations"
            >
              {sources.length === 0 ? (
                <EmptyState
                  title="No source excerpts"
                  description="This answer did not use any knowledge-base context."
                  icon="search"
                />
              ) : (
                <>
                  <div className="source-list">
                    {sources.map((source) => (
                      <button
                        type="button"
                        key={source.label}
                        className={
                          "source-row " + (selectedSource?.label === source.label ? "active" : "")
                        }
                        onClick={() => setSelectedLabel(source.label)}
                        aria-pressed={selectedSource?.label === source.label}
                      >
                        <span className="result-rank">{source.label}</span>
                        <span>
                          <strong>
                            Document {source.document_id.slice(0, 8)} · Chunk{" "}
                            {source.chunk_index + 1}
                          </strong>
                          <small>
                            Retrieval rank #{source.retrieval_rank} · offsets {source.start_offset}–
                            {source.end_offset}
                            {source.page_start != null
                              ? ` · PDF page ${source.page_start}${source.page_end !== source.page_start ? "–" + source.page_end : ""}`
                              : ""}
                            {source.ocr_used ? " · OCR" : ""}
                          </small>
                        </span>
                        <Icon name="chevron-right" size={15} />
                      </button>
                    ))}
                  </div>
                  {selectedSource ? (
                    <div className="rag-live-evidence">
                      <div className="rag-live-evidence-meta">
                        <strong>{selectedSource.label} · saved source excerpt</strong>
                        <small>Chunk UUID: {selectedSource.chunk_id}</small>
                        <small>Document UUID: {selectedSource.document_id}</small>
                        <small>
                          Source offsets: {selectedSource.start_offset}–{selectedSource.end_offset}
                        </small>
                        {selectedSource.page_start != null ? (
                          <small>
                            PDF page {selectedSource.page_start}
                            {selectedSource.page_end !== selectedSource.page_start
                              ? `–${selectedSource.page_end}`
                              : ""}
                            {selectedSource.ocr_used ? " · includes OCR text" : ""}
                          </small>
                        ) : null}
                      </div>
                      <pre className="rag-live-excerpt">{selectedSource.excerpt}</pre>
                      {selectedSource.ocr_used ? (
                        <p className="text-hint">
                          OCR-derived text can contain recognition errors; check the
                          original PDF before relying on this source.
                        </p>
                      ) : null}
                      <Link
                        className="button ghost compact"
                        href={`/chunks?kb=${base.id}&doc=${selectedSource.document_id}`}
                      >
                        <Icon name="layers" size={14} /> Inspect original document
                      </Link>
                    </div>
                  ) : null}
                </>
              )}
            </Panel>
          </div>
          <div className="inline-notice">
            <Icon name="info" size={16} />
            Source labels and excerpt inspection are available. Automated verification of answer
            claims against source evidence remains a separate future milestone (SP-23).
          </div>
        </>
      ) : !running && !error ? (
        <EmptyState
          title="No live answer yet"
          description="Choose a knowledge base, enter a question, and explicitly generate an answer. No demo responses or background model calls will appear."
          icon="sparkles"
        />
      ) : null}
    </div>
  );
}
