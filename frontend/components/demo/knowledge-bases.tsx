"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { KNOWLEDGE_BASES, type KnowledgeBase } from "@/lib/demo-data";

import { Icon } from "../icons";
import { PageHeading, Panel, SampleBadge } from "../ui";
import { useDemoToast } from "../workbench-shell";

export function KnowledgeBasesPage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([...KNOWLEDGE_BASES]);
  const [selected, setSelected] = useState<string>(KNOWLEDGE_BASES[0].id);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const notify = useDemoToast();
  const active = knowledgeBases.find((item) => item.id === selected) ?? knowledgeBases[0];

  function addKnowledgeBase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const created: KnowledgeBase = {
      id: "demo-" + Date.now(),
      name: trimmed,
      description: "Empty collection created for this local preview.",
      documents: 0,
      chunks: 0,
      category: "Custom",
      updated: "Just now",
    };
    setKnowledgeBases((items) => [created, ...items]);
    setSelected(created.id);
    setName("");
    setCreating(false);
    notify("Collection added to demo preview only. No server data changed.");
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="SOURCE COLLECTIONS"
        title="Knowledge bases"
        description="Your source collections, index health, and document coverage in one place."
        badge="Sample collections"
        action={
          <button type="button" className="button primary" onClick={() => setCreating(true)}>
            <Icon name="plus" size={16} /> New knowledge base
          </button>
        }
      />

      <div className="kb-grid">
        {knowledgeBases.map((kb) => (
          <button
            key={kb.id}
            type="button"
            className={"knowledge-card " + (selected === kb.id ? "selected" : "")}
            onClick={() => setSelected(kb.id)}
            aria-pressed={selected === kb.id}
          >
            <span className="kb-card-icon"><Icon name="database" size={22} /></span>
            <strong>{kb.name}</strong>
            <p>{kb.description}</p>
            <div className="kb-category">{kb.category} · {kb.updated}</div>
            <div className="kb-card-footer">
              <span><Icon name="file" size={14} /> {kb.documents} docs</span>
              <span><Icon name="layers" size={14} /> {kb.chunks.toLocaleString()} chunks</span>
            </div>
          </button>
        ))}
      </div>

      <div className="dashboard-grid">
        <Panel
          title={active.name}
          hint="Selected collection · illustrative summary"
          action={<SampleBadge>Preview details</SampleBadge>}
        >
          <div className="kb-detail">
            <span className="kb-detail-icon"><Icon name="database" size={28} /></span>
            <div>
              <strong>{active.description}</strong>
              <p>Source collection details and actions will connect to FastAPI in SP-10.</p>
            </div>
          </div>
          <div className="kb-detail-stats">
            <span><strong>{active.documents}</strong><small>Documents</small></span>
            <span><strong>{active.chunks.toLocaleString()}</strong><small>Indexed chunks</small></span>
            <span><strong>{active.documents ? "Ready" : "Empty"}</strong><small>Index status</small></span>
          </div>
          <Link href="/chunks" className="button ghost compact">
            Inspect sample chunks <Icon name="arrow-right" size={15} />
          </Link>
        </Panel>
        <Panel title="Processing overview" hint="Demonstration of the future health view">
          <div className="pipeline-grid">
            {([
              ["file", "124", "Documents"],
              ["layers", "18,431", "Chunks"],
              ["check", "98.7%", "Indexed"],
              ["clock", "143 ms", "Query p95"],
            ] as const).map(([icon, value, label]) => (
              <div className="pipeline-step" key={label}>
                <span className="pipeline-icon"><Icon name={icon} size={17} /></span>
                <strong>{value}</strong>
                <small>{label}</small>
              </div>
            ))}
          </div>
          <div className="muted-panel-note">
            Statistics are sample values and are not fetched from your knowledge bases.
          </div>
        </Panel>
      </div>

      {creating ? (
        <div className="dialog-backdrop" onMouseDown={() => setCreating(false)}>
          <section
            className="simple-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="New demo knowledge base"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="dialog-heading">
              <div><h2>New knowledge base</h2><p>Create a sample collection in this browser session.</p></div>
              <button type="button" className="icon-button" onClick={() => setCreating(false)} aria-label="Close dialog">
                <Icon name="x" size={17} />
              </button>
            </div>
            <form onSubmit={addKnowledgeBase}>
              <label className="field-label" htmlFor="kb-name">Collection name</label>
              <input
                autoFocus
                id="kb-name"
                className="input-control"
                maxLength={60}
                required
                placeholder="e.g. Architecture reference"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <p className="text-hint">Demo only · nothing will be saved to PostgreSQL.</p>
              <div className="dialog-actions">
                <button type="button" className="button ghost" onClick={() => setCreating(false)}>Cancel</button>
                <button type="submit" className="button primary">Create in preview</button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </div>
  );
}
