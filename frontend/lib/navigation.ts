export type WorkbenchRoute =
  | "/"
  | "/knowledge-bases"
  | "/retrieval"
  | "/chunks"
  | "/evaluations"
  | "/traces"
  | "/rag"
  | "/settings";

export type NavigationIcon =
  | "layout"
  | "database"
  | "search"
  | "layers"
  | "chart"
  | "clock"
  | "sparkles"
  | "settings";

export interface NavigationItem {
  label: string;
  href: WorkbenchRoute;
  icon: NavigationIcon;
  description: string;
  shortcut?: string;
}

export const NAVIGATION_GROUPS: ReadonlyArray<{
  label: string;
  items: ReadonlyArray<NavigationItem>;
}> = [
  {
    label: "Workspace",
    items: [
      { label: "Overview", href: "/", icon: "layout", description: "Workspace overview", shortcut: "01" },
      { label: "Knowledge bases", href: "/knowledge-bases", icon: "database", description: "Source collections" },
      { label: "Retrieval lab", href: "/retrieval", icon: "search", description: "Inspect ranked evidence", shortcut: "⌘ 2" },
      { label: "Chunk inspector", href: "/chunks", icon: "layers", description: "Document versions and excerpts" },
    ],
  },
  {
    label: "Observability",
    items: [
      { label: "Evaluations", href: "/evaluations", icon: "chart", description: "Quality metrics and benchmarks" },
      { label: "Trace history", href: "/traces", icon: "clock", description: "Saved retrieval decisions" },
      { label: "RAG answers", href: "/rag", icon: "sparkles", description: "Grounded answer inspection" },
    ],
  },
  {
    label: "Preferences",
    items: [{ label: "Settings", href: "/settings", icon: "settings", description: "Workspace appearance and integration" }],
  },
];

export const NAVIGATION_ITEMS: ReadonlyArray<NavigationItem> = NAVIGATION_GROUPS.flatMap(
  (group) => group.items,
);

export function routeLabel(pathname: string): string {
  return NAVIGATION_ITEMS.find((item) => item.href === pathname)?.label ?? "Workspace";
}
