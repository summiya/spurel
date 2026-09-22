import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Spurel",
  description: "Visual debugging and evaluation for RAG retrieval.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
