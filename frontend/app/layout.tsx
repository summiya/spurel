import type { Metadata } from "next";

import { WorkbenchShell } from "@/components/workbench-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: "Spurel | Retrieval Intelligence",
  description: "Explore retrieval evidence, trace rankings and measure RAG quality.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark">
      <body>
        <WorkbenchShell>{children}</WorkbenchShell>
      </body>
    </html>
  );
}
