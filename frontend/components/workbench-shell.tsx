"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { NAVIGATION_GROUPS, routeLabel } from "@/lib/navigation";

import { CommandPalette } from "./command-palette";
import { Icon } from "./icons";

type Theme = "dark" | "light";
type ThemeValue = { theme: Theme; setTheme: (theme: Theme) => void };

const ThemeContext = createContext<ThemeValue>({
  theme: "dark",
  setTheme: () => undefined,
});
const ToastContext = createContext<(message: string) => void>(() => undefined);

export function useWorkbenchTheme() {
  return useContext(ThemeContext);
}

export function useDemoToast() {
  return useContext(ToastContext);
}

function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Spurel home">
      <span className="brand-mark" aria-hidden="true">
        <i /><i /><i /><i />
      </span>
      <span>
        <span className="brand-word">SPUREL</span>
        <span className="brand-subline">RETRIEVAL<br />INTELLIGENCE</span>
      </span>
    </Link>
  );
}

export function WorkbenchShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>("dark");
  const [toast, setToast] = useState<string | null>(null);

  const notify = useCallback((message: string) => setToast(message), []);

  useEffect(() => {
    const saved = window.localStorage.getItem("spurel-theme");
    if (saved !== "dark" && saved !== "light") return;
    // Restore browser preference after hydration without changing server markup.
    const frame = window.requestAnimationFrame(() => setTheme(saved));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("spurel-theme", theme);
  }, [theme]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((visible) => !visible);
      } else if (event.key === "Escape") {
        setPaletteOpen(false);
        setMobileOpen(false);
      } else if ((event.metaKey || event.ctrlKey) && event.key === "2") {
        event.preventDefault();
        router.push("/retrieval");
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [router]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <ToastContext.Provider value={notify}>
        <div className="workspace-shell">
          {mobileOpen ? (
            <button
              className="mobile-scrim"
              type="button"
              aria-label="Close navigation"
              onClick={() => setMobileOpen(false)}
            />
          ) : null}
          <aside className={"sidebar " + (mobileOpen ? "mobile-visible" : "")}>
            <Brand />
            <nav className="sidebar-navigation" aria-label="Main navigation">
              {NAVIGATION_GROUPS.map((group) => (
                <div className="sidebar-group" key={group.label}>
                  <div className="sidebar-group-label">{group.label}</div>
                  {group.items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      aria-current={pathname === item.href ? "page" : undefined}
                      className={"nav-link " + (pathname === item.href ? "active" : "")}
                    >
                      <Icon name={item.icon} size={17} />
                      <span>{item.label}</span>
                      {item.shortcut ? <small>{item.shortcut}</small> : null}
                    </Link>
                  ))}
                </div>
              ))}
            </nav>
            <div className="sidebar-bottom">
              <div className="usage-card">
                <div className="usage-head"><strong>Workspace usage</strong><span>58%</span></div>
                <div className="usage-track"><i /></div>
                <p>Illustrative metrics · not live</p>
              </div>
              <div className="sidebar-profile">
                <span className="profile-avatar">SP</span>
                <span><strong>Demo workspace</strong><small>Design preview · local only</small></span>
              </div>
            </div>
          </aside>

          <div className="workspace-main">
            <header className="topbar">
              <div className="topbar-left">
                <button
                  type="button"
                  className="icon-button mobile-menu-button"
                  aria-label="Open navigation"
                  aria-expanded={mobileOpen}
                  onClick={() => setMobileOpen((visible) => !visible)}
                >
                  <Icon name="menu" />
                </button>
                <div className="breadcrumbs">
                  <span>Workspace</span><span className="breadcrumb-divider">/</span>
                  <strong>{routeLabel(pathname)}</strong>
                </div>
              </div>
              <div className="topbar-right">
                <button
                  type="button"
                  className="command-trigger"
                  aria-label="Open command search"
                  onClick={() => setPaletteOpen(true)}
                >
                  <Icon name="search" size={15} />
                  <span>Jump to anything</span>
                  <kbd>⌘ K</kbd>
                </button>
                <span className="top-demo-pill"><span /> INTERACTIVE DEMO</span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                  title="Change theme"
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                >
                  <Icon name={theme === "dark" ? "moon" : "sun"} size={17} />
                </button>
                <span className="top-avatar" aria-label="Demo profile">S</span>
              </div>
            </header>
            <main id="main-content" className="page-content" tabIndex={-1}>
              {children}
              <footer className="page-footer">
                SPUREL DESIGN PREVIEW · ALL METRICS AND DOCUMENTS ARE ILLUSTRATIVE
              </footer>
            </main>
          </div>
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
          {toast ? (
            <div className="toast-message" role="status" aria-live="polite">
              <Icon name="check" size={16} />
              {toast}
              <button type="button" aria-label="Dismiss notification" onClick={() => setToast(null)}>
                <Icon name="x" size={14} />
              </button>
            </div>
          ) : null}
        </div>
      </ToastContext.Provider>
    </ThemeContext.Provider>
  );
}
