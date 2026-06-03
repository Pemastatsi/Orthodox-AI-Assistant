import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { CLERK_ENABLED } from "@/lib/auth-config";
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
  const document = (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
  // In dev mode (no Clerk key) the app renders without ClerkProvider so it needs no Clerk config.
  return CLERK_ENABLED ? <ClerkProvider>{document}</ClerkProvider> : document;
}
