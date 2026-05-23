import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orthodox AI Assistant",
  description: "Closed-corpus theological Q&A — Phase 1 scaffold.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
