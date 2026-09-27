// API response types (tolerant: server is the source of truth).

export type Role = "ADMIN" | "LEAD_INVESTIGATOR" | "INVESTIGATOR" | "AUDITOR";

export interface Me {
  id: string;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at?: string;
}

export interface Investigation {
  id: string;
  name: string;
  description?: string | null;
  target_host: string;
  target_os?: string;
  source_mode: "DATASET" | "LIVE_LOCAL" | string;
  source_path?: string | null;
  provenance: "LIVE" | "SYNTHETIC" | string;
  status: "OPEN" | "IN_PROGRESS" | "CLOSED" | string;
  created_by: string;
  created_at: string | null;
  evidence_count?: number;
  open_jobs?: number;
  evidence_summary?: { total: number; by_type: Record<string, number> };
  last_activity?: string | null;
  recent_jobs?: Array<{ id: string; status: string; fql: string; completed_at: string | null }>;
}

export interface EvidenceItem {
  id: string;
  evidence_type: string;
  collected_at: string | null;
  data_hash: string;
  data: Record<string, unknown>;
  provenance: string;
  blockchain_status: string;
  blockchain_tx?: string | null;
  raw_file_path?: string | null;
  integrity?: { matches_stored: boolean; recomputed_hash?: string };
}

export interface Finding {
  id: string;
  investigation_id: string;
  execution_id?: string | null;
  analysis_id?: string | null;
  source: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO" | string;
  title: string;
  description?: string;
  evidence_ids: string[];
  mitre_techniques?: string[] | null;
  status: "OPEN" | "VERIFIED" | "DISMISSED" | string;
  created_at: string | null;
}

export interface TimelineEntry {
  timestamp: string;
  type: string;
  label: string;
  evidence_id: string;
  severity?: string | null;
  provenance?: string | null;
}

export interface GraphData {
  nodes: Array<{ id: string; type: string; data: { label: string; [k: string]: unknown } }>;
  edges: Array<{ id: string; source: string; target: string; label: string; type: string }>;
}

export interface Execution {
  id: string;
  script_id?: string | null;
  investigation_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMEOUT" | "SANDBOX_VIOLATION" | "PARTIAL" | string;
  started_at?: string | null;
  completed_at?: string | null;
  findings_count?: number;
  console_log?: string[] | null;
  resource_usage?: { user_cpu_sec?: number; system_cpu_sec?: number; max_rss_mb?: number } | null;
  error_message?: string | null;
}

export interface ExecutionDetail extends Execution {
  findings?: Finding[];
}

export interface Script {
  id: string;
  name: string;
  language: string;
  version: number;
  template_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScriptDetail extends Script {
  code: string;
  description?: string | null;
  investigation_id: string;
  last_execution?: Execution | null;
}

export interface Template {
  id: string;
  title: string;
  name?: string;
  description: string;
  category: string;
  code: string;
  language: string;
  params?: Array<{ name: string; type?: string; description?: string; default?: unknown }>;
  expected_output?: string;
  forensic_context?: string;
  examples?: string[];
  error_handling?: string;
  docs?: string;
}

export interface AiAnalysis {
  id: string;
  analysis_type: "CORRELATION" | "QUERY_RESPONSE" | string;
  engine?: string | null;
  model_used?: string | null;
  confidence_score?: number | null;
  result?: (CorrelationResult & { answer?: string; evidence_refs?: string[]; caveat?: string | null }) | null;
  input_evidence_ids?: string[] | null;
  created_at?: string | null;
}

export interface SuspiciousIndicator {
  indicator: string;
  severity: string;
  evidence_ids: string[];
  stage?: string | null;
  technique?: string | null;
}

export interface CorrelationResult {
  what_happened: string;
  confidence: number;
  suspicious_indicators: SuspiciousIndicator[];
  attack_stages: Array<{ stage: string; evidence_ids: string[]; summary?: string }>;
  mitre_techniques: Array<{ technique_id: string; name?: string; evidence_ids?: string[] }>;
  gaps: string[];
  engine?: string;
  caveat?: string | null;
}

export interface Report {
  id: string;
  title: string;
  report_type: "FULL" | "SUMMARY" | "CHAIN_OF_CUSTODY" | string;
  status: "PENDING" | "GENERATING" | "READY" | "FAILED" | string;
  file_size_bytes?: number | null;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface AuditRow {
  id: string;
  created_at: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  result: string;
  ip_address?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface JobStatus {
  job_id: string;
  status: string;
  kind?: string;
  progress?: number;
  items_collected_so_far?: number;
  collectors?: Record<string, string>;
  error?: string | null;
  result?: Record<string, unknown>;
}

export interface DashboardStats {
  active_cases: number;
  evidence_items: number;
  executions: number;
  findings: number;
  high_severity_findings: number;
  severity_distribution: Record<string, number>;
  artifact_categories: Record<string, number>;
  execution_history: Array<{ date: string; count: number }>;
}

export interface Dataset {
  id: string;
  files: string[];
  size_bytes: number;
}

export interface Paginated<T> {
  data: T[];
  pagination: { page: number; per_page: number; total: number };
}
