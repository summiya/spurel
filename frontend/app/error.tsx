"use client";

import { ErrorState } from "@/components/ui";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <ErrorState
      title="This workspace view couldn't load"
      description="Your other views are still available. Try loading this page again."
      onRetry={reset}
    />
  );
}
