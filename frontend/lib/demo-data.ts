export type RetrievalMode = "hybrid" | "vector" | "keyword";
export type SampleTopic = "auth" | "refund" | "backup";

export interface Evidence {
  id: string;
  name: string;
  text: string;
  tag: string;
  chunk: number;
  offsets: string;
  vector: number;
  keyword: number;
  hybrid: number;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  documents: number;
  chunks: number;
  category: string;
  updated: string;
}

export const KNOWLEDGE_BASES: ReadonlyArray<KnowledgeBase> = [
  {
    id: "engineering",
    name: "Engineering docs",
    description: "Architecture, API references, authentication and platform notes.",
    documents: 124,
    chunks: 8420,
    category: "Engineering",
    updated: "2 hours ago",
  },
  {
    id: "policy",
    name: "Policy library",
    description: "Internal workflows, approvals and employee policies.",
    documents: 68,
    chunks: 4812,
    category: "Operations",
    updated: "Yesterday",
  },
  {
    id: "support",
    name: "Support handbook",
    description: "Customer help guides, playbooks and troubleshooting notes.",
    documents: 42,
    chunks: 3112,
    category: "Support",
    updated: "3 days ago",
  },
  {
    id: "product",
    name: "Product knowledge",
    description: "Product releases, feature guides and documented decisions.",
    documents: 31,
    chunks: 2102,
    category: "Product",
    updated: "5 days ago",
  },
];

export const PRESETS: ReadonlyArray<{ label: string; query: string; topic: SampleTopic }> = [
  {
    label: "Passwordless auth",
    query: "How does passwordless authentication work?",
    topic: "auth",
  },
  { label: "Refund policy", query: "What is our refund approval policy?", topic: "refund" },
  { label: "Backup recovery", query: "How do we restore from backup?", topic: "backup" },
];

const auth: ReadonlyArray<Evidence> = [
  {
    id: "auth-01",
    name: "authentication-architecture.md",
    text: "Our passwordless authentication flow sends a short-lived email challenge. Successful verification creates an authenticated session and invalidates the challenge.",
    tag: "auth · architecture",
    chunk: 3,
    offsets: "1,200–1,361",
    vector: 0.96,
    keyword: 0.82,
    hybrid: 0.94,
  },
  {
    id: "auth-02",
    name: "security-guidelines.md",
    text: "One-time login challenges expire after a configurable TTL. Requests must use nonce validation and replay protection for the full session lifecycle.",
    tag: "security · guidelines",
    chunk: 2,
    offsets: "830–977",
    vector: 0.91,
    keyword: 0.88,
    hybrid: 0.92,
  },
  {
    id: "auth-03",
    name: "session-management.md",
    text: "The server issues session credentials after a successful challenge response. Session renewal and revocation follow the authentication policy.",
    tag: "session · backend",
    chunk: 8,
    offsets: "490–633",
    vector: 0.88,
    keyword: 0.9,
    hybrid: 0.89,
  },
  {
    id: "auth-04",
    name: "identity-faq.md",
    text: "A user can choose a passkey or sign-in email to access their account without memorizing a password. Rate limiting protects the challenge endpoint.",
    tag: "identity · FAQ",
    chunk: 1,
    offsets: "420–590",
    vector: 0.77,
    keyword: 0.76,
    hybrid: 0.8,
  },
  {
    id: "auth-05",
    name: "api-standards.md",
    text: "The authentication API offers endpoints to request and validate challenges, and session ownership is verified for every protected operation.",
    tag: "api · standards",
    chunk: 4,
    offsets: "780–980",
    vector: 0.74,
    keyword: 0.79,
    hybrid: 0.76,
  },
  {
    id: "auth-06",
    name: "access-audit.md",
    text: "Monitoring records challenge creation, sign-in verification and session termination for security reviews and operational diagnostics.",
    tag: "audit · security",
    chunk: 6,
    offsets: "205–357",
    vector: 0.71,
    keyword: 0.66,
    hybrid: 0.72,
  },
];

const refund: ReadonlyArray<Evidence> = [
  {
    id: "refund-01",
    name: "refund-policy.md",
    text: "Refunds are available within thirty days of purchase. Requests outside this window require manager approval and a documented exception.",
    tag: "policies · refunds",
    chunk: 2,
    offsets: "410–574",
    vector: 0.97,
    keyword: 0.94,
    hybrid: 0.98,
  },
  {
    id: "refund-02",
    name: "approval-matrix.md",
    text: "Refund exceptions above the standard threshold must be approved by the support manager before payment reversal.",
    tag: "approvals · finance",
    chunk: 4,
    offsets: "1,021–1,170",
    vector: 0.9,
    keyword: 0.92,
    hybrid: 0.94,
  },
  {
    id: "refund-03",
    name: "customer-care.md",
    text: "Support staff verify the order status, original payment and refund eligibility before raising a request for review.",
    tag: "support · process",
    chunk: 3,
    offsets: "720–870",
    vector: 0.87,
    keyword: 0.83,
    hybrid: 0.89,
  },
  {
    id: "refund-04",
    name: "billing-operations.md",
    text: "Approved refunds are reconciled with the original transaction and reflected on the customer statement.",
    tag: "payments · billing",
    chunk: 1,
    offsets: "290–446",
    vector: 0.83,
    keyword: 0.76,
    hybrid: 0.84,
  },
  {
    id: "refund-05",
    name: "policy-faq.md",
    text: "Customers can check the refund status using their original transaction reference and support ticket number.",
    tag: "help · FAQ",
    chunk: 5,
    offsets: "655–790",
    vector: 0.75,
    keyword: 0.69,
    hybrid: 0.76,
  },
  {
    id: "refund-06",
    name: "order-lifecycle.md",
    text: "Order cancellation requests follow a separate workflow before shipment, with different refund timing.",
    tag: "orders · status",
    chunk: 2,
    offsets: "170–325",
    vector: 0.71,
    keyword: 0.61,
    hybrid: 0.7,
  },
];

const backup: ReadonlyArray<Evidence> = [
  {
    id: "backup-01",
    name: "backup-procedures.md",
    text: "Database backups are taken on a schedule and copied to isolated storage. A recovery drill confirms every snapshot can be restored.",
    tag: "recovery · operations",
    chunk: 2,
    offsets: "260–435",
    vector: 0.97,
    keyword: 0.93,
    hybrid: 0.98,
  },
  {
    id: "backup-02",
    name: "disaster-recovery.md",
    text: "Restore the most recent verified snapshot to an isolated environment before promoting recovery traffic to production.",
    tag: "infra · reliability",
    chunk: 6,
    offsets: "1,180–1,344",
    vector: 0.91,
    keyword: 0.88,
    hybrid: 0.93,
  },
  {
    id: "backup-03",
    name: "database-maintenance.md",
    text: "After recovery, validate schema migrations, foreign keys, data integrity and the application readiness endpoint.",
    tag: "postgres · database",
    chunk: 3,
    offsets: "540–718",
    vector: 0.86,
    keyword: 0.84,
    hybrid: 0.89,
  },
  {
    id: "backup-04",
    name: "incident-playbook.md",
    text: "The incident owner documents root cause, service impact, recovery duration and follow-up mitigation work.",
    tag: "incident · runbook",
    chunk: 5,
    offsets: "920–1,084",
    vector: 0.82,
    keyword: 0.73,
    hybrid: 0.82,
  },
  {
    id: "backup-05",
    name: "storage-retention.md",
    text: "Backup retention schedules depend on environment, sensitivity and recovery objectives for the data set.",
    tag: "storage · retention",
    chunk: 3,
    offsets: "530–680",
    vector: 0.76,
    keyword: 0.71,
    hybrid: 0.77,
  },
  {
    id: "backup-06",
    name: "reliability-checklist.md",
    text: "Run periodic restore tests and confirm the team can locate current credentials and recovery documentation.",
    tag: "SRE · checklist",
    chunk: 1,
    offsets: "100–257",
    vector: 0.71,
    keyword: 0.63,
    hybrid: 0.7,
  },
];

export const DEMO_EVIDENCE: Record<SampleTopic, ReadonlyArray<Evidence>> = {
  auth,
  refund,
  backup,
};

export function topicForQuery(query: string): SampleTopic {
  const normalized = query.toLowerCase();
  if (/refund|return policy|approval/.test(normalized)) return "refund";
  if (/backup|restore|recovery|disaster/.test(normalized)) return "backup";
  return "auth";
}

export function rankedEvidence(query: string, mode: RetrievalMode, topK: number): Evidence[] {
  const topic = topicForQuery(query);
  const limit = Math.max(1, Math.min(6, Math.trunc(topK)));
  return [...DEMO_EVIDENCE[topic]].sort((a, b) => b[mode] - a[mode]).slice(0, limit);
}

export function formatDemoScore(score: number): string {
  return (score * 100).toFixed(1) + "%";
}

export interface SampleDocument {
  id: string;
  name: string;
  description: string;
  updated: string;
  versions: number;
  chunks: readonly string[];
}

export const DEMO_DOCUMENTS: ReadonlyArray<SampleDocument> = [
  {
    id: "authentication",
    name: "authentication-architecture.md",
    description: "Sign-in flows and secure session design",
    updated: "2 hours ago",
    versions: 2,
    chunks: [
      "A passwordless sign-in challenge is issued with a short expiry and single-use nonce.",
      "The verification endpoint checks the nonce, expiry and challenge status before issuing a session.",
      "Session renewal, logout and audit events protect access throughout the credential lifecycle.",
    ],
  },
  {
    id: "security",
    name: "security-guidelines.md",
    description: "Replay protection and permission boundaries",
    updated: "Yesterday",
    versions: 3,
    chunks: [
      "Login challenges are single-use and never logged in raw form.",
      "Protected operations validate the authentication context for every request.",
      "Security telemetry records challenge failures, retries and unusual sessions.",
    ],
  },
  {
    id: "refunds",
    name: "refund-policy.md",
    description: "Support approval and reimbursement rules",
    updated: "3 days ago",
    versions: 2,
    chunks: [
      "Refunds are available within thirty days after purchase.",
      "Requests outside the eligible window require written manager approval.",
      "Payment reversals are reconciled against the original order transaction.",
    ],
  },
];

export interface DemoTrace {
  id: string;
  query: string;
  mode: RetrievalMode;
  count: number;
  ms: number;
  ago: string;
  kb: string;
  topic: SampleTopic;
}

export const DEMO_TRACES: ReadonlyArray<DemoTrace> = [
  {
    id: "TR-1048",
    query: PRESETS[0].query,
    mode: "hybrid",
    count: 4,
    ms: 124,
    ago: "2 minutes ago",
    kb: "Engineering docs",
    topic: "auth",
  },
  {
    id: "TR-1047",
    query: PRESETS[1].query,
    mode: "keyword",
    count: 3,
    ms: 86,
    ago: "1 hour ago",
    kb: "Policy library",
    topic: "refund",
  },
  {
    id: "TR-1046",
    query: PRESETS[2].query,
    mode: "vector",
    count: 5,
    ms: 117,
    ago: "3 hours ago",
    kb: "Engineering docs",
    topic: "backup",
  },
  {
    id: "TR-1045",
    query: "Describe the session expiry rules.",
    mode: "hybrid",
    count: 4,
    ms: 138,
    ago: "Yesterday",
    kb: "Engineering docs",
    topic: "auth",
  },
];

export const DEMO_RUNS = [
  {
    id: "RUN-029",
    name: "Authentication regression",
    mode: "Hybrid",
    recall: 94.2,
    precision: 88.1,
    mrr: 0.92,
    status: "Passed",
    date: "Today",
  },
  {
    id: "RUN-028",
    name: "Refund policy baseline",
    mode: "Keyword",
    recall: 89.6,
    precision: 82.4,
    mrr: 0.87,
    status: "Passed",
    date: "Yesterday",
  },
  {
    id: "RUN-027",
    name: "Recovery documentation",
    mode: "Vector",
    recall: 91.7,
    precision: 84.8,
    mrr: 0.89,
    status: "Review",
    date: "2 days ago",
  },
] as const;
