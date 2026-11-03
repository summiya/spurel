export interface LiveKnowledgeBase {
  id: string;
  name: string;
  created_at: string;
}

export interface LiveDocument {
  id: string;
  knowledge_base_id: string;
  filename: string;
  media_type: "application/pdf" | "text/plain" | "text/markdown";
  size_bytes: number;
  created_at: string;
  active_chunk_version: number;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
}

export interface ProcessedDocument {
  status: "processed";
  document_id: string;
  knowledge_base_id: string;
  chunk_count: number;
  embedded_chunk_count: number;
  chunk_version: number;
  reused_active_version: boolean;
}
