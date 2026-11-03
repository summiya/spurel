"use client";

import { useState } from "react";

import { Icon } from "../icons";
import { PageHeading, Panel } from "../ui";
import { useDemoToast, useWorkbenchTheme } from "../workbench-shell";

export function SettingsPage() {
  const { theme, setTheme } = useWorkbenchTheme();
  const [compact, setCompact] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const notify = useDemoToast();

  return (
    <div className="screen">
      <PageHeading
        eyebrow="WORKSPACE PREFERENCES"
        title="Settings"
        description="Make Spurel comfortable to inspect, navigate and experiment in."
        badge="Local preferences"
      />
      <div className="dashboard-grid">
        <Panel title="Appearance" hint="Select an interface theme">
          <div className="settings-field">
            <div>
              <strong>Color theme</strong>
              <p>Choose the dark observability theme or a lighter workspace.</p>
            </div>
            <div className="segmented-control" role="group" aria-label="Color theme">
              <button
                type="button"
                className={"segment-button " + (theme === "dark" ? "selected" : "")}
                aria-pressed={theme === "dark"}
                onClick={() => setTheme("dark")}
              >
                <Icon name="moon" size={15} /> Dark
              </button>
              <button
                type="button"
                className={"segment-button " + (theme === "light" ? "selected" : "")}
                aria-pressed={theme === "light"}
                onClick={() => setTheme("light")}
              >
                <Icon name="sun" size={15} /> Light
              </button>
            </div>
          </div>
          <div className="settings-field">
            <div>
              <strong>Compact tables</strong>
              <p>Preview an option for future dense engineering views.</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={compact}
              aria-label="Compact tables"
              className={"switch-control " + (compact ? "enabled" : "")}
              onClick={() => {
                setCompact((value) => !value);
                notify("Compact tables preference changed for this demo.");
              }}
            >
              <span />
            </button>
          </div>
          <div className="settings-field last">
            <div>
              <strong>Reduce motion</strong>
              <p>Disable decorative UI transitions in this preview.</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={reducedMotion}
              aria-label="Reduce motion"
              className={"switch-control " + (reducedMotion ? "enabled" : "")}
              onClick={() => {
                setReducedMotion((value) => !value);
                document.documentElement.dataset.motion = valueToMotion(!reducedMotion);
              }}
            >
              <span />
            </button>
          </div>
        </Panel>
        <Panel title="Backend connection" hint="Security and integration boundaries">
          <div className="connection-status">
            <Icon name="shield" size={21} />
            <div>
              <strong>Server-only API integration</strong>
              <p>
                Protected upstream endpoints are intentionally not exposed to anonymous browser
                sessions.
              </p>
            </div>
          </div>
          <div className="pipeline-detail">
            <span>UI data source</span>
            <span className="status-badge">Illustrative fixtures</span>
          </div>
          <div className="pipeline-detail">
            <span>Shared API bearer token</span>
            <span className="status-badge success">Not in browser</span>
          </div>
          <div className="pipeline-detail last">
            <span>Sources, chunks, retrieval and trace comparisons</span>
            <span className="status-badge success">Live · SP-10–13</span>
          </div>
          <p className="muted-panel-note">
            SP-10–SP-13 connect sources, chunk inspection, retrieval and saved trace comparisons to
            FastAPI. Evaluations and RAG answers remain demo screens. Never put your API token in
            NEXT_PUBLIC_* settings.
          </p>
        </Panel>
      </div>
      <Panel title="About Spurel" hint="Pre-alpha frontend foundation">
        <div className="about-grid">
          <span>
            <Icon name="layout" size={19} />
            <strong>Responsive workspace</strong>
            <small>Sidebar navigation and keyboard command search</small>
          </span>
          <span>
            <Icon name="chart" size={19} />
            <strong>Inspectable by design</strong>
            <small>Retrieval, chunks and evaluations in one shell</small>
          </span>
          <span>
            <Icon name="shield" size={19} />
            <strong>Safe data boundaries</strong>
            <small>No provider secrets in the demonstration</small>
          </span>
        </div>
      </Panel>
    </div>
  );
}

function valueToMotion(reduced: boolean): string {
  return reduced ? "reduce" : "normal";
}
