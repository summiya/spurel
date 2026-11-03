"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { NAVIGATION_ITEMS } from "@/lib/navigation";

import { Icon } from "./icons";

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const matches = useMemo(() => {
    const term = query.trim().toLowerCase();
    return NAVIGATION_ITEMS.filter((item) =>
      (item.label + " " + item.description).toLowerCase().includes(term),
    );
  }, [query]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  function goTo(href: string) {
    router.push(href);
    onClose();
    setQuery("");
    setSelected(0);
  }

  return (
    <div className="dialog-backdrop" onMouseDown={onClose}>
      <section
        className="command-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Jump to a Spurel page"
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          } else if (event.key === "ArrowDown") {
            event.preventDefault();
            setSelected((index) => Math.min(matches.length - 1, index + 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setSelected((index) => Math.max(0, index - 1));
          } else if (event.key === "Enter" && matches[selected]) {
            event.preventDefault();
            goTo(matches[selected].href);
          }
        }}
      >
        <div className="command-search">
          <Icon name="search" size={19} />
          <input
            ref={inputRef}
            aria-label="Search pages"
            placeholder="Search pages and actions..."
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelected(0);
            }}
          />
          <button type="button" onClick={onClose} aria-label="Close command palette">
            Esc
          </button>
        </div>
        <div className="command-results">
          <p className="command-group">JUMP TO</p>
          {matches.length ? (
            matches.map((item, index) => (
              <button
                key={item.href}
                type="button"
                className={"command-option " + (index === selected ? "selected" : "")}
                onMouseEnter={() => setSelected(index)}
                onClick={() => goTo(item.href)}
              >
                <span className="command-option-icon">
                  <Icon name={item.icon} size={17} />
                </span>
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                <Icon name="arrow-right" size={16} />
              </button>
            ))
          ) : (
            <p className="command-empty">No matching pages</p>
          )}
        </div>
        <div className="command-footer">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> Navigate
          </span>
          <span>
            <kbd>↵</kbd> Open
          </span>
          <span>
            <kbd>esc</kbd> Close
          </span>
        </div>
      </section>
    </div>
  );
}
