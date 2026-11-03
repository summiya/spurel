import Link from "next/link";

import { EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="This workspace view doesn't exist."
      icon="search"
      action={<Link href="/" className="button primary">Return to overview</Link>}
    />
  );
}
