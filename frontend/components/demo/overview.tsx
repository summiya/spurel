"use client";

import Link from "next/link";
import { useState } from "react";

import { DEMO_TRACES } from "@/lib/demo-data";

import { Icon } from "../icons";
import { MetricCard, PageHeading, Panel } from "../ui";

function QualityChart({ days }: { days: 7 | 30 }) {
  const recall =
    days === 7
      ? "M0 145 C55 129 80 158 120 114 S206 131 258 96 S350 116 394 70 S475 95 520 56 S565 76 600 33"
      : "M0 164 C36 153 60 141 90 144 S140 116 180 125 S240 111 280 106 S340 91 380 85 S445 70 480 62 S550 63 600 32";
  const precision =
    days === 7
      ? "M0 164 C70 153 90 150 121 136 S231 151 269 121 S368 124 411 108 S503 124 600 80"
      : "M0 175 C60 171 90 157 130 157 S210 145 260 141 S330 132 380 114 S440 121 495 97 S565 96 600 78";

  return (
    <svg
      viewBox="0 0 600 190"
      preserveAspectRatio="none"
      role="img"
      aria-label={"Illustrative recall and precision trend over " + days + " days"}
      className="quality-chart"
    >
      <defs>
        <linearGradient id="recall-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6ee7f6" stopOpacity=".25" />
          <stop offset="1" stopColor="#6ee7f6" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[36, 77, 118, 159].map((y) => (
        <path key={y} d={"M0 " + y + "H600"} className="chart-gridline" />
      ))}
      <path d={recall + " V190 H0 Z"} fill="url(#recall-fill)" />
      <path d={recall} stroke="#6ee7f6" fill="none" strokeWidth="3" />
      <path d={precision} stroke="#a78bfa" fill="none" strokeWidth="2" strokeDasharray="5 6" />
      <circle cx="599" cy={days === 7 ? 33 : 32} r="4" fill="#6ee7f6" />
    </svg>
  );
}

export function OverviewPage() {
  const [days, setDays] = useState<7 | 30>(7);

  return (
    <div className="screen">
      <PageHeading
        eyebrow="YOUR RAG CONTROL CENTER"
        title="Every retrieval decision. Visible."
        description="Understand what the system retrieved, why it ranked, and how it performed."
        action={
          <>
            <Link href="/evaluations" className="button ghost">View evaluations</Link>
            <Link href="/retrieval" className="button primary">
              <Icon name="zap" size={16} /> New experiment
            </Link>
          </>
        }
      />

      <section className="hero-banner">
        <div className="hero-content">
          <p className="eyebrow">RETRIEVAL, DECODED</p>
          <h2>Stop guessing why RAG works.</h2>
          <p>Go from black-box answers to explorable evidence, ranked results, and measurable quality.</p>
          <Link href="/retrieval" className="button ghost compact">
            Explore retrieval lab <Icon name="arrow-right" size={15} />
          </Link>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <span className="orbit-ring" />
          <span className="orbit-node first" />
          <span className="orbit-node second" />
          <span className="orbit-node third" />
          <span className="orbit-core" />
        </div>
      </section>

      <div className="metrics-grid">
        <MetricCard label="Knowledge bases" value="08" description="Across 3 workspaces · +2 new" icon="database" />
        <MetricCard label="Indexed chunks" value="18.4k" description="Ready for retrieval · 98.7%" icon="layers" />
        <MetricCard label="Recall @ 10" value="91.8%" description="↑ 3.6% against baseline" icon="chart" />
        <MetricCard label="p95 query latency" value="143ms" description="↓ 18ms against previous run" icon="zap" />
      </div>

      <div className="dashboard-grid">
        <Panel
          title="Retrieval quality over time"
          hint="Illustrative performance trend · not backend data"
          action={
            <select
              value={days}
              aria-label="Chart time window"
              className="select-control compact"
              onChange={(event) => setDays(Number(event.target.value) === 30 ? 30 : 7)}
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
            </select>
          }
        >
          <QualityChart days={days} />
          <div className="chart-legend">
            <span><i className="legend-line cyan" /> Recall @ 10</span>
            <span><i className="legend-line purple" /> Precision @ 10</span>
            <span className="chart-period">Sample · {days} days</span>
          </div>
        </Panel>

        <Panel
          title="Ingestion pipeline"
          hint="Inspectable from source to searchable index."
          action={<span className="health-indicator"><i /> Healthy · demo</span>}
        >
          <div className="pipeline-grid">
            {([
              ["file", "Parse", "Document"],
              ["layers", "Chunk", "Segments"],
              ["sparkles", "Embed", "Vectors"],
              ["check", "Index", "Ready"],
            ] as const).map(([icon, name, detail]) => (
              <div className="pipeline-step" key={name}>
                <span className="pipeline-icon"><Icon name={icon} size={18} /></span>
                <strong>{name}</strong>
                <small>{detail}</small>
              </div>
            ))}
          </div>
          <div className="pipeline-detail">
            <span>Latest sample processing run</span>
            <span className="status-badge success">Complete</span>
          </div>
          <div className="pipeline-detail last">
            <span>Illustrative documents indexed</span>
            <strong>124 / 124</strong>
          </div>
        </Panel>
      </div>

      <div className="dashboard-grid">
        <Panel
          title="Recent retrievals"
          action={
            <Link href="/traces" className="button ghost compact">
              View all traces <Icon name="arrow-right" size={15} />
            </Link>
          }
        >
          <div className="recent-list">
            {DEMO_TRACES.slice(0, 3).map((trace, index) => (
              <Link href="/traces" key={trace.id} className="recent-item">
                <span className="recent-icon"><Icon name="search" size={17} /></span>
                <span className="recent-body">
                  <strong>{trace.query}</strong>
                  <small>{trace.mode} · {trace.kb} · {trace.ago}</small>
                </span>
                <strong className="recent-score">{["94.2%", "89.6%", "91.7%"][index]}</strong>
              </Link>
            ))}
          </div>
        </Panel>
        <Panel title="Jump into your workflow" action={<span className="text-hint">Quick actions</span>}>
          <div className="quick-list">
            {([
              ["/knowledge-bases", "database", "Browse knowledge bases"],
              ["/chunks", "layers", "Inspect document chunks"],
              ["/retrieval", "search", "Debug a retrieval"],
              ["/evaluations", "chart", "Compare evaluations"],
            ] as const).map(([href, icon, label]) => (
              <Link key={href} href={href} className="quick-item">
                <Icon name={icon} size={17} />
                <span>{label}</span>
                <Icon name="arrow-up-right" size={14} />
              </Link>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
