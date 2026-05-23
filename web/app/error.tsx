"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Real error reporting wiring lands in T-006 alongside the i18n error catalog.
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h2 className="text-xl font-semibold">Something went wrong.</h2>
      <button
        type="button"
        onClick={() => reset()}
        className="mt-4 rounded bg-gray-900 px-4 py-2 text-sm text-white"
      >
        Try again
      </button>
    </main>
  );
}
