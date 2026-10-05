export type ClaimStatus = "VERIFIED_CODE" | "VERIFIED_TEST" | "DOCUMENTED" | "CORROBORATED" | "INFERRED" | "CONFLICT" | "UNKNOWN";

export type SourceCard = {
  id: string;
  type: "code" | "documentation";
  title: string;
  path: string;
  start_line: number;
  end_line: number;
  page: number | null;
  heading_path: string[];
  excerpt: string;
  source_snapshot_id: string;
  document_version: number | null;
  status: "current" | "stale" | "unknown";
};

export type SourceExcerpt = {
  repo_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  content: string;
  source_snapshot_id: string;
  redacted: boolean;
  truncated: boolean;
};

export type DocCodeLink = {
  id: string;
  doc_section_id: string;
  code_entity_id: string;
  code_name: string;
  file_path: string;
  start_line: number | null;
  end_line: number | null;
  relation: "REFERENCES";
  provenance: "exact_symbol" | "exact_path" | "exact_route" | "exact_config";
  verification: "exact_reference";
  reference: string;
  graph_snapshot_id: string;
  stale: boolean;
};

export type DocumentSection = {
  id: string;
  document_id: string;
  document_title: string;
  version: number;
  authoritative: boolean;
  parent_id: string | null;
  level: number;
  ordinal: number;
  heading_path: string[];
  content_type: "text" | "code" | "table" | "mixed";
  content: string;
  source: SourceCard;
  code_links: DocCodeLink[];
};

export type DocumentSearchResponse = {
  repo_id: string;
  query: string;
  results: DocumentSection[];
  limit: number;
  retrieval: "lexical";
};

export type IngestDocumentResponse = {
  repo_id: string;
  document_id: string;
  version: number;
  path: string;
  checksum: string;
  section_count: number;
  link_count: number;
  changed: boolean;
  redacted: boolean;
  parser: "native_markdown" | "native_text" | "native_pdf";
  warnings: string[];
};

export type DocumentVersion = {
  document_id: string;
  version: number;
  checksum: string;
  title: string;
  authoritative: boolean;
  parser: string;
  created_at: string;
  section_count: number;
};

export type BrainStatus = {
  repo_id: string;
  project_name: string;
  mode: "read_only";
  graph_snapshot_id: string;
  code_node_count: number;
  code_edge_count: number;
  document_count: number;
  section_count: number;
  link_count: number;
  stale_link_count: number;
  artifact_count: number;
  document_formats: string[];
  capabilities: string[];
  limitations: string[];
};

export type EvidenceClaim = {
  id: string;
  claim: string;
  status: ClaimStatus;
  evidence_ids: string[];
  note: string;
};

export type GraphArtifactNode = {
  id: string;
  name: string;
  type: string;
  file_path: string;
  start_line: number | null;
  end_line: number | null;
  source_id: string | null;
  documentation_ids: string[];
  description: string;
};

export type GraphArtifactEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  is_inferred: boolean;
  provenance: string;
};

export type WalkthroughStep = {
  node_id: string;
  title: string;
  explanation: string;
  source_ids: string[];
  next_node_ids: string[];
};

export type GraphArtifactSpec = {
  nodes: GraphArtifactNode[];
  edges: GraphArtifactEdge[];
  mermaid: string;
  steps: WalkthroughStep[];
  truncated: boolean;
};

export type BrainArtifact = {
  id: string;
  type: "architecture_graph" | "interactive_walkthrough";
  title: string;
  source: "deterministic_graph";
  version: number;
  source_snapshot_id: string;
  created_at: string;
  spec: GraphArtifactSpec;
};

export type ArtifactListResponse = { repo_id: string; artifacts: BrainArtifact[] };

export type BrainAnswer = {
  answer_id: string;
  repo_id: string;
  mode: "teach" | "walkthrough";
  summary: string;
  sections: Array<{ type: "prose" | "note" | "warning"; title: string; markdown: string }>;
  artifacts: BrainArtifact[];
  claims: EvidenceClaim[];
  sources: SourceCard[];
  suggested_actions: string[];
  graph_snapshot_id: string;
  generated_by: "deterministic_evidence";
};
