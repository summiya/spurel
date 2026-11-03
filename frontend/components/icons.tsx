import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "layout" | "database" | "search" | "layers" | "chart" | "clock"
  | "sparkles" | "settings" | "menu" | "moon" | "sun" | "arrow-right"
  | "chevron-down" | "file" | "check" | "play" | "zap" | "shield"
  | "x" | "plus" | "command" | "filter" | "terminal" | "upload"
  | "copy" | "refresh" | "alert" | "info" | "arrow-up-right"
  | "chevron-right" | "book" | "activity";

const drawings: Record<IconName, ReactNode> = {
  layout: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m16.5 16.5 4 4" /></>,
  layers: <path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5" />,
  chart: <path d="M3 3v18h18M7 16l4-5 4 2 5-8" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  sparkles: <path d="m12 2 2.6 7.4L22 12l-7.4 2.6L12 22l-2.6-7.4L2 12l7.4-2.6L12 2Z" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M10 2h4l.6 2.5 2 1 2.4-.9 2 3.4-1.8 1.8v2.4l1.8 1.8-2 3.4-2.4-.9-2 1L14 22h-4l-.6-2.5-2-1-2.4.9-2-3.4 1.8-1.8v-2.4L3 9.9l2-3.4 2.4.9 2-1L10 2Z" /></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  "arrow-right": <path d="M4 12h16m-6-6 6 6-6 6" />,
  "chevron-down": <path d="m6 9 6 6 6-6" />,
  "chevron-right": <path d="m9 6 6 6-6 6" />,
  file: <path d="M5 2h9l5 5v15H5V2Zm9 0v6h5M8 13h8M8 17h8" />,
  check: <path d="m4 12 5 5L20 6" />,
  play: <path d="m8 5 11 7-11 7V5Z" />,
  zap: <path d="m13 2-9 11h7l-1 9 10-12h-7V2Z" />,
  shield: <path d="m12 2 8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5l8-3Zm-4 10 3 3 5-6" />,
  x: <path d="M5 5l14 14M19 5 5 19" />,
  plus: <path d="M12 4v16M4 12h16" />,
  command: <><path d="M9 7V5a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v14a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V7Z" /></>,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  terminal: <path d="m4 6 6 6-6 6M13 18h7" />,
  upload: <path d="M12 16V3m-5 5 5-5 5 5M4 16v4h16v-4" />,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M5 16H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v1" /></>,
  refresh: <path d="M20 7v5h-5M4 17v-5h5M5.5 9a7 7 0 0 1 12-2l2.5 3M4 14l2.5 3a7 7 0 0 0 12-2" />,
  alert: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v5m0 3v.2" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8v.5" /></>,
  "arrow-up-right": <path d="M7 17 17 7M8 7h9v9" />,
  book: <><path d="M4 5c3-2 5-2 8 0 3-2 5-2 8 0v15c-3-2-5-2-8 0-3-2-5-2-8 0V5Z" /><path d="M12 5v15" /></>,
  activity: <path d="M2 12h4l3-7 6 14 3-7h4" />,
};

export function Icon({
  name,
  size = 18,
  className,
  ...props
}: {
  name: IconName;
  size?: number;
} & Omit<SVGProps<SVGSVGElement>, "name" | "children">) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
      {...props}
    >
      {drawings[name]}
    </svg>
  );
}
