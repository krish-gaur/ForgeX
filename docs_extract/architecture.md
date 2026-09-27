

FORGE-X — Production Architecture Document

# ⚙ FORGE-X

 Production Architecture v1.0

 Overview
 01 · Requirements
 02 · Product Workflows
 Architecture
 03 · System Architecture
 04 · Technology Stack
 05 · Database Schema
 Contracts
 06 · API Specification
 07 · Frontend Architecture
 08 · Backend Architecture
 Subsystems
 09 · AI Architecture
 10 · Security Architecture
 11 · Scalability Plan
 12 · Testing Strategy
 Delivery
 13 · MVP Scope
 14 · Implementation Roadmap
 15 · Cursor Handoff
 16 · OpenCode Handoff
 17 · Risks
 18 · Definition of Done

# FORGE-X — System Architecture

SIH26148 · Theme: Blockchain & Cybersecurity · Team: AlGloryThm · Lead Architect Document v1.0

## 01 Requirements

### Problem Statement (Exact)

 SIH26148: Security controls (EDR, AV, Firewall) designed to stop attackers also interrupt and block legitimate forensic tools run by authorized investigators. When an investigator tries to collect evidence — processes, files, users, network activity, system events — the security stack flags the collection activity as suspicious and disrupts it. This forces investigators to use fragmented manual tools, results in missed evidence, and makes incident reconstruction slow and incomplete.

### Target Users

 User RoleContextPrimary Need

 Lead InvestigatorEnterprise IR / Law Enforcement Cyber UnitRun and manage full investigations; approve FQL execution

 InvestigatorAuthorized digital forensic analystWrite FQL queries, collect evidence, view correlation results

 AuditorCompliance / Legal officerReview investigation audit trail, verify evidence integrity

 AdminFORGE-X platform administratorManage users, configure policies, manage target systems

### Prioritized Requirements

 PriorityRequirementSource

 MUSTFQL (Forensic Query Language) — simple DSL to express investigation intentSlide 2,3

 MUSTPolicy-controlled execution layer — validates every collector call before executionSlide 2,4

 MUSTProcess collector (Windows + Linux)Slide 2,3

 MUSTFile system collector (Windows + Linux)Slide 2,3

 MUSTNetwork activity collector (PCAP / Zeek)Slide 3

 MUSTUser activity collectorSlide 2,3

 MUSTSystem event collector (Windows EventLog / Linux syslog/auditd)Slide 2,3

 MUSTSHA-256 integrity hashing of every evidence item at collection timeSlide 2

 MUSTEvidence stored in PostgreSQL (structured) + Neo4j (graph correlations)Slide 3

 MUSTTimeline visualization of all collected eventsSlide 2,3

 MUSTEvidence graph (USER→PROCESS→FILE→NETWORK→EVENT)Slide 2

 MUSTLLM-powered "What Happened?" incident reconstructionSlide 2,3

 MUSTFull audit log of all forensic actions takenSlide 4

 MUSTJWT-based authentication + RBAC (Admin, Lead, Investigator, Auditor)Derived

 MUSTInvestigation report generation (PDF)Slide 3

 SHOULDRAG over collected evidence for investigator Q&ASlide 3

 SHOULDMITRE ATT&CK technique mapping of correlated evidenceSlide 6

 SHOULDBlockchain-anchored evidence hashes (for SIH theme)SIH Theme

 SHOULDEvidence export (JSON, CSV)Derived

 NICEMulti-endpoint investigation (network-wide forensics)Slide 4

 NICEReal-time collection streaming via WebSocketDerived

 NICEMobile-responsive view for on-the-go monitoringDerived

 DO NOT BUILDEDR/AV bypass or evasion techniques — FORGE-X is an authorized tool, not an evasion toolEthics

 DO NOT BUILDMalware analysis sandboxOut of scope

 DO NOT BUILDVulnerability scanner / exploitation frameworkOut of scope

### Ambiguities / Flags

 Flag 1 — FQL Grammar Scope: The PPT does not define FQL syntax. This document specifies it fully in §08. Agents must NOT invent alternative grammar.

 Flag 2 — Deployment Target: PPT implies a local/on-premises tool, not cloud SaaS. FORGE-X runs as Docker containers on the investigator's workstation or an on-premises server. There is no multi-tenant cloud hosting in MVP.

 Flag 3 — Collector Execution Model: Collectors can run in two modes: (a) local — if the target is the same machine as FORGE-X; (b) remote SSH agent — if the target is a different endpoint. MVP targets local execution; SSH-based remote is SHOULD HAVE.

 Flag 4 — Blockchain Integration: The hackathon theme is "Blockchain & Cybersecurity" but the solution slides do not specify a blockchain implementation. Architecture adds evidence hash anchoring on Ethereum Sepolia testnet as a SHOULD HAVE for demo differentiation.

## 02 Product Workflows

### WF-01 · Investigator Starts New Investigation

 🕵️ Investigator logs in
→

 POST /investigations {name, target, description}
→

 Validate: name required, target IP/hostname required
→

 Create Investigation record, status=ACTIVE
→

 Audit log entry created
→

 Redirect to /investigations/:id

Failure: Duplicate name → 409 CONFLICT. Missing target → 422 UNPROCESSABLE.

### WF-02 · Write and Execute FQL Query

 Investigator writes FQL
→

 POST /fql/validate (syntax check)
→

 POST /fql/execute
→

 Policy Engine evaluates request
→

 Forensic Orchestrator spawns collectors
→

 Evidence collected → hashed → stored
→

 Job ID returned → frontend polls status
→

 Evidence appears in dashboard

Failure paths: Policy denied → 403 with reason. Collector timeout (30s) → partial evidence saved, job status=PARTIAL. Target unreachable → 503. FQL parse error → 422 with line/column.

### WF-03 · Evidence Correlation (AI)

 Investigator clicks "Correlate"
→

 POST /investigations/:id/ai/correlate
→

 Evidence items loaded from PostgreSQL
→

 Relationships queried from Neo4j
→

 Context built for LLM (RAG retrieval)
→

 LLM generates structured correlation result
→

 Result validated (JSON schema)
→

 Stored + displayed in dashboard

Failure paths: LLM timeout → retry x2, then return partial result with flag. No evidence → 400 "Collect evidence first". Invalid LLM output → discard, return error, do NOT show hallucinated output.

### WF-04 · Generate Investigation Report

 Investigator clicks "Generate Report"
→

 POST /investigations/:id/reports
→

 Background job queued (Celery)
→

 Job: fetch evidence + correlations + AI analysis
→

 LLM generates narrative summary
→

 PDF rendered (WeasyPrint)
→

 Stored, download link returned
→

 Notification to investigator

### WF-05 · Auditor Reviews Evidence Integrity

 Auditor logs in (role: AUDITOR)
→

 GET /investigations/:id/evidence (read-only)
→

 For each item: verify SHA-256 matches stored hash
→

 Optional: verify blockchain anchor hash (Sepolia)
→

 GET /investigations/:id/audit-log
→

 Download chain-of-custody report

## 03 System Architecture

Deployment model: Modular monolith running in Docker Compose on the investigator's workstation or an on-premises server. The forensic collectors run as Python sub-processes (local) or over SSH (remote). No cloud SaaS dependency in MVP.

### Architecture Diagram

```

graph TB
 subgraph BROWSER["🖥 Investigator Browser"]
 UI["Next.js App
(FQL Editor · Dashboard · Timeline · Graph)"]
 end

 subgraph GATEWAY["API Gateway · Port 8000"]
 NGINX["Nginx Reverse Proxy
(TLS, rate-limit, CORS)"]
 end

 subgraph APP["FORGE-X Backend · FastAPI"]
 AUTH["Auth Service
(JWT · RBAC)"]
 FQL["FQL Parser/Validator
(Lark grammar)"]
 POLICY["Policy Engine
(YAML rules)"]
 ORCH["Forensic Orchestrator
(Job Manager)"]
 EVID["Evidence Service
(hash · store · index)"]
 AI["AI / Intelligence Service
(LLM · RAG · Correlator)"]
 REPORT["Report Service
(PDF generator)"]
 AUDIT["Audit Logger"]
 WS["WebSocket Hub
(job status updates)"]
 end

 subgraph WORKERS["Celery Workers"]
 W1["Collector Worker"]
 W2["AI Worker"]
 W3["Report Worker"]
 end

 subgraph COLLECTORS["Forensic Collectors"]
 PC["Process Collector
(psutil / WMI)"]
 FC["File Collector
(os.walk)"]
 NC["Network Collector
(PCAP / Zeek)"]
 UC["User Collector
(pwd / SAM)"]
 EC["Event Collector
(EventLog / syslog/auditd)"]
 TC["Timeline Builder"]
 end

 subgraph DATA["Data Layer"]
 PG[("PostgreSQL 16
(investigations · evidence · users · audit)")]
 NEO[("Neo4j 5
(evidence graph · correlations)")]
 REDIS[("Redis 7
(cache · job queue · sessions)")]
 FS["File Store
(PCAP · memory dumps · reports)"]
 VEC[("pgvector
(evidence embeddings for RAG)")]
 end

 subgraph AI_EXT["AI / External"]
 LLM["LLM Provider
(OpenAI GPT-4o / Anthropic Claude)"]
 BC["Blockchain Anchor
(Ethereum Sepolia testnet)"]
 end

 subgraph TARGET["Target System"]
 WIN["Windows Agent
(PowerShell / WMI / ETW)"]
 LINUX["Linux Agent
(bash / proc / auditd)"]
 end

 UI -->|HTTPS/WS| NGINX
 NGINX --> AUTH
 NGINX --> FQL
 NGINX --> ORCH
 NGINX --> EVID
 NGINX --> AI
 NGINX --> REPORT
 NGINX --> WS

 FQL --> POLICY
 POLICY --> ORCH
 ORCH -->|enqueue| REDIS
 REDIS -->|dequeue| W1
 W1 --> PC & FC & NC & UC & EC & TC
 PC & FC & NC --> WIN
 PC & FC & NC & UC & EC --> LINUX

 ORCH --> AUDIT
 W1 --> EVID
 EVID --> PG
 EVID --> NEO
 EVID --> FS
 EVID --> VEC
 EVID -->|hash anchor| BC

 W2 --> AI
 AI --> LLM
 AI --> VEC

 W3 --> REPORT
 REPORT --> FS

 AUTH --> PG
 AUDIT --> PG

### Component Responsibilities

 ComponentResponsibilityKey Constraint

 NginxTLS termination, CORS, rate limiting (100 req/min/IP), static file serving for Next.jsMust not log Authorization headers

 Auth ServiceJWT issuance (HS256, 1h access token, 7d refresh), RBAC enforcement middlewareRefresh tokens stored in Redis; revocable

 FQL ParserParses FQL text into structured AST using Lark grammar; returns parse errors with line/colNo execution occurs in parser — parse only

 Policy EngineEvaluates collector request against YAML policy rules. Grants or denies with reason codePolicy loaded from DB at startup; cached in Redis 60s

 Forensic OrchestratorTranslates approved FQL AST into collector jobs; enqueues to Redis/Celery; tracks job statusEach FQL execution = one Job with N sub-tasks

 Evidence ServiceReceives raw collector output; SHA-256 hashes it; stores in PostgreSQL; creates Neo4j nodes/edges; indexes embeddings in pgvectorHash computed before any DB write; immutable after write

 AI ServiceBuilds RAG context from pgvector; calls LLM with structured prompt; validates output JSON schema; stores resultProvider key NEVER leaves backend; output validated before storage

 Report ServiceFetches all investigation data, calls AI for narrative, renders PDF via WeasyPrintRuns as background Celery task; report stored in FS

 Audit LoggerAppends immutable audit entries (who, when, what, result) to PostgreSQL audit_logs tableSync write; cannot be disabled by any user role

 WebSocket HubPushes job status updates to investigator browser in real timeAuth required via WS handshake token

## 04 Technology Stack

 LayerTechnologyWhyMVP?

 FrontendNext.js 15 (App Router, TypeScript)Specified in tech stack slide. SSR for report pages, RSC for fast dashboard. Strong TypeScript ecosystem for type-safe API integration.✅ Yes

 UI ComponentsTailwind CSS + shadcn/uiRapid development; forensic dashboard needs dense data tables and cards. Accessible by default.✅ Yes

 Graph VisualizationReact Flow (evidence graph) + D3.js (timeline)React Flow renders interactive node graphs for USER→PROCESS→FILE chains. D3 for time-series timeline.✅ Yes

 State ManagementZustand + React Query (TanStack)Zustand for global investigation state. React Query for server-state caching, polling, and optimistic updates.✅ Yes

 BackendPython 3.12 + FastAPISpecified in tech stack slide. Async-native, auto OpenAPI docs, excellent ecosystem for system-level scripting (psutil, scapy, etc.)✅ Yes

 FQL ParserLark (Python parsing toolkit)Clean EBNF grammar definition. Produces an AST. Gives precise error positions. Pure Python — no external service.✅ Yes

 Task QueueCelery 5 + RedisCollector jobs are async (can take 5-60s). Celery handles retries, timeouts, and worker concurrency. Redis as broker.✅ Yes

 Primary DBPostgreSQL 16 + pgvectorSpecified in tech stack slide. Structured evidence storage, ACID compliance for chain-of-custody. pgvector eliminates need for separate vector DB in MVP.✅ Yes

 Graph DBNeo4j 5 CommunitySpecified in tech stack slide. Cypher queries for USER→PROCESS→FILE→NETWORK→EVENT correlation. Essential for "incident story" feature.✅ Yes

 Cache / QueueRedis 7Job queue broker (Celery), session store, policy cache, WebSocket pub/sub. One service, multiple purposes.✅ Yes

 Network CapturePCAP (libpcap/pyshark) + ZeekSpecified in tech stack slide. Zeek transforms raw PCAP into structured connection logs, DNS, HTTP, SSL records.✅ Yes

 LLMAnthropic Claude claude-sonnet-4-6 (primary) / OpenAI GPT-4o (fallback)Structured output support, function calling, long context for evidence summaries. Provider abstraction layer handles fallback.✅ Yes

 PDF ReportsWeasyPrintRenders HTML→PDF with full CSS support. No external service needed. Runs in backend.✅ Yes

 Blockchain Anchorweb3.py + Ethereum Sepolia testnetSIH theme requirement. Evidence hash + timestamp submitted to Sepolia. Provides verifiable, tamper-evident chain-of-custody proof.⚡ Demo

 ContainerDocker ComposeSingle-command deployment. All services (FastAPI, Postgres, Neo4j, Redis, Nginx) in one compose file. No Kubernetes needed for MVP.✅ Yes

 AuthPyJWT + passlib (bcrypt)Lightweight, no external OAuth service needed. JWT with RS256 for production, HS256 for dev.✅ Yes

 Process Forensicspsutil (cross-platform), python-evtx (Windows events)Cross-platform process/memory collection. python-evtx parses Windows Event Log .evtx files.✅ Yes

## 05 Database Schema

### PostgreSQL Schema

```
-- Users and Auth
CREATE TABLE users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 email VARCHAR(255) UNIQUE NOT NULL,
 username VARCHAR(100) UNIQUE NOT NULL,
 password_hash VARCHAR(255) NOT NULL, -- bcrypt
 role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN','LEAD_INVESTIGATOR','INVESTIGATOR','AUDITOR')),
 is_active BOOLEAN DEFAULT TRUE,
 created_at TIMESTAMPTZ DEFAULT NOW(),
 updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

-- Investigations (Cases)
CREATE TABLE investigations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 name VARCHAR(255) NOT NULL,
 description TEXT,
 target_host VARCHAR(255) NOT NULL, -- IP or hostname of target system
 target_os VARCHAR(20) CHECK (target_os IN ('WINDOWS','LINUX','UNKNOWN')),
 status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','COMPLETED','ARCHIVED','SUSPENDED')),
 created_by UUID NOT NULL REFERENCES users(id),
 lead_investigator UUID REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT NOW(),
 updated_at TIMESTAMPTZ DEFAULT NOW(),
 closed_at TIMESTAMPTZ
);
CREATE INDEX idx_investigations_created_by ON investigations(created_by);
CREATE INDEX idx_investigations_status ON investigations(status);

-- Policies
CREATE TABLE policies (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 name VARCHAR(100) UNIQUE NOT NULL,
 description TEXT,
 rules JSONB NOT NULL, -- Policy YAML parsed to JSON
 is_default BOOLEAN DEFAULT FALSE,
 is_active BOOLEAN DEFAULT TRUE,
 created_by UUID NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT NOW()
);

-- FQL Queries (submitted by investigator)
CREATE TABLE fql_queries (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
 raw_fql TEXT NOT NULL,
 parsed_ast JSONB, -- AST output from parser
 status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING','VALIDATED','POLICY_DENIED','QUEUED','RUNNING','COMPLETED','FAILED','PARTIAL')),
 policy_decision JSONB, -- Policy engine response
 submitted_by UUID NOT NULL REFERENCES users(id),
 submitted_at TIMESTAMPTZ DEFAULT NOW(),
 completed_at TIMESTAMPTZ,
 error_message TEXT
);
CREATE INDEX idx_fql_investigation ON fql_queries(investigation_id);

-- Collector Executions (one per collector per FQL query)
CREATE TABLE collector_executions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 fql_query_id UUID NOT NULL REFERENCES fql_queries(id) ON DELETE CASCADE,
 collector_type VARCHAR(30) NOT NULL CHECK (collector_type IN ('PROCESS','FILE','NETWORK','USER','EVENT','TIMELINE')),
 status VARCHAR(20) DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','COMPLETED','FAILED','TIMEOUT','SKIPPED')),
 started_at TIMESTAMPTZ DEFAULT NOW(),
 completed_at TIMESTAMPTZ,
 items_collected INT DEFAULT 0,
 error_message TEXT,
 raw_params JSONB -- Params derived from FQL AST
);

-- Evidence Items (core entity)
CREATE TABLE evidence_items (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
 execution_id UUID REFERENCES collector_executions(id),
 evidence_type VARCHAR(30) NOT NULL CHECK (evidence_type IN ('PROCESS','FILE','NETWORK_CONNECTION','USER_ACCOUNT','SYSTEM_EVENT','TIMELINE_ENTRY','PCAP_FILE','LOG_ENTRY')),
 collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 target_host VARCHAR(255) NOT NULL,
 data JSONB NOT NULL, -- Structured evidence payload
 data_hash VARCHAR(64) NOT NULL, -- SHA-256 of data field (hex)
 raw_file_path VARCHAR(500), -- If evidence is a file (PCAP etc.)
 blockchain_tx VARCHAR(100), -- Sepolia tx hash (optional)
 blockchain_status VARCHAR(20) DEFAULT 'NOT_SUBMITTED' CHECK (blockchain_status IN ('NOT_SUBMITTED','PENDING','CONFIRMED','FAILED')),
 embedding_id INT, -- pgvector reference
 collected_by UUID NOT NULL REFERENCES users(id),
 CONSTRAINT unique_evidence_hash UNIQUE (investigation_id, data_hash)
);
CREATE INDEX idx_evidence_investigation ON evidence_items(investigation_id);
CREATE INDEX idx_evidence_type ON evidence_items(evidence_type);
CREATE INDEX idx_evidence_collected_at ON evidence_items(collected_at);

-- pgvector embeddings for RAG
CREATE TABLE evidence_embeddings (
 id SERIAL PRIMARY KEY,
 evidence_id UUID NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
 embedding vector(1536), -- OpenAI text-embedding-3-small
 text_content TEXT, -- Human-readable representation used for embedding
 created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_embeddings_evidence ON evidence_embeddings(evidence_id);
-- Vector similarity index (IVFFlat)
CREATE INDEX idx_embeddings_vector ON evidence_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- AI Correlation Results
CREATE TABLE ai_analyses (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
 analysis_type VARCHAR(30) NOT NULL CHECK (analysis_type IN ('CORRELATION','EXPLANATION','QUERY_RESPONSE','MITRE_MAPPING')),
 prompt_tokens INT,
 completion_tokens INT,
 model_used VARCHAR(50),
 input_evidence_ids UUID[], -- Evidence items used as context
 result JSONB NOT NULL, -- Structured LLM output
 confidence_score FLOAT, -- 0.0-1.0 if model provides
 created_by UUID NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Investigation Reports
CREATE TABLE investigation_reports (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
 title VARCHAR(255),
 report_type VARCHAR(20) DEFAULT 'FULL' CHECK (report_type IN ('FULL','SUMMARY','CHAIN_OF_CUSTODY')),
 status VARCHAR(20) DEFAULT 'GENERATING' CHECK (status IN ('GENERATING','READY','FAILED')),
 file_path VARCHAR(500), -- Path to PDF in file store
 file_size_bytes BIGINT,
 created_by UUID NOT NULL REFERENCES users(id),
 created_at TIMESTAMPTZ DEFAULT NOW(),
 completed_at TIMESTAMPTZ
);

-- Audit Log (immutable)
CREATE TABLE audit_logs (
 id BIGSERIAL PRIMARY KEY,
 actor_id UUID REFERENCES users(id),
 actor_email VARCHAR(255), -- Denormalized for permanence
 action VARCHAR(100) NOT NULL, -- e.g. INVESTIGATION_CREATED, FQL_EXECUTED
 resource_type VARCHAR(50),
 resource_id VARCHAR(100),
 metadata JSONB,
 ip_address INET,
 user_agent TEXT,
 result VARCHAR(20) CHECK (result IN ('SUCCESS','FAILURE','DENIED')),
 created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);

### Neo4j Schema (Graph)

```
// Node labels and properties
(:User { id, username, host, sid_or_uid, last_login, evidence_id })
(:Process { id, pid, name, cmdline, user, parent_pid, started_at, hash_md5, hash_sha256, evidence_id })
(:File { id, path, size, hash_sha256, modified_at, created_at, accessed_at, evidence_id })
(:NetworkConn { id, src_ip, src_port, dst_ip, dst_port, protocol, bytes, started_at, evidence_id })
(:SystemEvent { id, event_id, event_type, description, timestamp, evidence_id })

// Relationship types
(:User)-[:LAUNCHED]->(:Process) // User started process
(:Process)-[:SPAWNED]->(:Process) // Parent→child process
(:Process)-[:ACCESSED_FILE]->(:File) // Process read/wrote file
(:Process)-[:MADE_CONNECTION]->(:NetworkConn) // Process initiated network
(:Process)-[:TRIGGERED_EVENT]->(:SystemEvent) // Process caused an event
(:User)-[:TRIGGERED_EVENT]->(:SystemEvent) // User caused an event
(:File)-[:LOADED_BY]->(:Process) // DLL/library loaded
(:NetworkConn)-[:RESOLVED_FROM]->(:SystemEvent) // DNS resolution event

// Relationship properties: { investigation_id, detected_at, confidence }

// Key Cypher queries used by Correlation Engine:
// 1. Find all processes spawned by a user:
MATCH (u:User {evidence_id:$uid})-[:LAUNCHED]->(p:Process) RETURN p

// 2. Full incident chain starting from suspicious process:
MATCH path = (u:User)-[:LAUNCHED]->(p:Process)-[:MADE_CONNECTION|ACCESSED_FILE*1..3]->()
WHERE p.name CONTAINS $suspicious_name RETURN path

// 3. Lateral movement detection:
MATCH (p:Process)-[:MADE_CONNECTION]->(n:NetworkConn)
WHERE n.dst_ip <> $local_subnet RETURN p, n

### Entity Relationship Diagram

```

erDiagram
 users ||--o{ investigations : "creates"
 users ||--o{ fql_queries : "submits"
 users ||--o{ evidence_items : "collects"
 users ||--o{ ai_analyses : "triggers"
 users ||--o{ audit_logs : "generates"

 investigations ||--o{ fql_queries : "contains"
 investigations ||--o{ evidence_items : "holds"
 investigations ||--o{ ai_analyses : "has"
 investigations ||--o{ investigation_reports : "produces"

 fql_queries ||--o{ collector_executions : "spawns"
 collector_executions ||--o{ evidence_items : "produces"
 evidence_items ||--o{ evidence_embeddings : "has"

 policies {
 uuid id PK
 string name
 jsonb rules
 bool is_default
 }
 users {
 uuid id PK
 string email
 string role
 bool is_active
 }
 investigations {
 uuid id PK
 string name
 string target_host
 string target_os
 string status
 }
 fql_queries {
 uuid id PK
 text raw_fql
 jsonb parsed_ast
 string status
 }
 collector_executions {
 uuid id PK
 string collector_type
 string status
 int items_collected
 }
 evidence_items {
 uuid id PK
 string evidence_type
 jsonb data
 string data_hash
 string blockchain_tx
 }
 evidence_embeddings {
 int id PK
 vector embedding
 text text_content
 }
 ai_analyses {
 uuid id PK
 string analysis_type
 jsonb result
 float confidence_score
 }
 investigation_reports {
 uuid id PK
 string status
 string file_path
 }
 audit_logs {
 bigint id PK
 string action
 string resource_type
 string result
 timestamptz created_at
 }

## 06 API Specification

Base URL: https://forgex.local/api/v1 · Auth: Authorization: Bearer <JWT> · Content-Type: application/json

### Standard Error Format

```
{
 "error": {
 "code": "POLICY_DENIED", // Machine-readable code
 "message": "Collector 'network' requires LEAD_INVESTIGATOR role",
 "details": { "collector": "network", "required_role": "LEAD_INVESTIGATOR" },
 "request_id": "req_01J8KP..." // For support/audit
 }
}

### Auth Endpoints

 POST /auth/login — Authenticate and receive tokens

#### Request

```
{ "username": "j.doe", "password": "hunter2" }

#### Response 200

```
{ "access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 3600,
 "user": { "id": "uuid", "username": "j.doe", "role": "INVESTIGATOR" } }

#### Errors
 401 invalid credentials · 403 account disabled

 POST /auth/refresh — Refresh access token

#### Request

```
{ "refresh_token": "eyJ..." }

#### Response 200

```
{ "access_token": "eyJ...", "expires_in": 3600 }

#### Errors
 401 expired/revoked refresh token

### Investigations

 GET /investigations — List investigations (paginated)

#### Auth
 Any authenticated role

#### Query Params
 status, page=1, per_page=20, search

#### Response 200

```
{ "data": [{ "id":"uuid","name":"DataBreach-2026-09","target_host":"192.168.1.50",
 "target_os":"LINUX","status":"ACTIVE","created_by":"j.doe","created_at":"2026-09-26T10:00:00Z",
 "evidence_count":142,"open_jobs":0 }],
 "pagination": { "page":1,"per_page":20,"total":3 } }

 POST /investigations — Create investigation

#### Auth
 INVESTIGATOR, LEAD_INVESTIGATOR, ADMIN

#### Request

```
{ "name":"DataBreach-2026-09","description":"Suspicious exfil detected",
 "target_host":"192.168.1.50","target_os":"LINUX" }

#### Response 201
 Full investigation object

#### Errors
 409 duplicate name · 422 validation

#### Side Effects
 audit_log entry: INVESTIGATION_CREATED

 GET /investigations/:id — Get full investigation detail

#### Response 200

```
{ "id":"uuid","name":"...","status":"ACTIVE","target_host":"192.168.1.50",
 "evidence_summary": {"total":142,"by_type":{"PROCESS":30,"FILE":45,"NETWORK_CONNECTION":20,...}},
 "last_activity":"2026-09-26T12:30:00Z",
 "recent_jobs": [{"id":"uuid","status":"COMPLETED","fql":"INVESTIGATE processes","completed_at":"..."}] }

### FQL Execution

 POST /investigations/:id/fql/validate — Syntax-check FQL without executing

#### Request

```
{ "fql": "INVESTIGATE processes WHERE name CONTAINS 'powershell'" }

#### Response 200

```
{ "valid":true, "ast":{"type":"INVESTIGATE","collector":"processes",
 "where":{"field":"name","op":"CONTAINS","value":"powershell"}},
 "estimated_collectors":["PROCESS"], "policy_preview":{"status":"ALLOWED"} }

#### Response 422

```
{ "error":{"code":"FQL_PARSE_ERROR","message":"Unexpected token at line 1, col 21",
 "details":{"line":1,"col":21,"token":"WHERE2"}} }

 POST /investigations/:id/fql/execute — Execute FQL query

#### Auth
 INVESTIGATOR+; network/memory collectors require LEAD_INVESTIGATOR

#### Request

```
{ "fql": "INVESTIGATE processes WHERE name CONTAINS 'powershell' AND user = 'SYSTEM'", "policy_id": "uuid-optional" }

#### Response 202 (Accepted)

```
{ "job_id":"job_01J8...", "fql_query_id":"uuid",
 "collectors":["PROCESS"], "estimated_duration_sec":15,
 "status_endpoint":"/api/v1/jobs/job_01J8.../status" }

#### Response 403 (Policy denied)

```
{ "error":{"code":"POLICY_DENIED","message":"Network capture requires case approval",
 "details":{"required_approval_from":"LEAD_INVESTIGATOR"}} }

#### Side Effects
 Creates fql_query record, enqueues Celery job, opens WebSocket notification channel

 GET /jobs/:job_id/status — Poll job status

#### Response 200

```
{ "job_id":"job_01J8...","status":"RUNNING","progress":{"completed":2,"total":3},
 "collectors":{"PROCESS":"COMPLETED","FILE":"RUNNING","NETWORK":"PENDING"},
 "items_collected_so_far":47 }

### Evidence

 GET /investigations/:id/evidence — List evidence (paginated, filterable)

#### Query Params
 type, from_time, to_time, search, page, per_page

#### Response 200

```
{ "data":[{ "id":"uuid","evidence_type":"PROCESS","collected_at":"2026-09-26T10:15:00Z",
 "data_hash":"sha256hex","data":{"pid":4567,"name":"powershell.exe","user":"SYSTEM",
 "cmdline":"powershell -enc YWRk...","parent_pid":1234,"parent_name":"cmd.exe"},
 "blockchain_status":"CONFIRMED","blockchain_tx":"0x..." }],
 "pagination":{...} }

 GET /investigations/:id/timeline — Chronological event timeline

#### Query Params
 from_time, to_time, granularity=minute|hour

#### Response 200

```
{ "timeline":[{ "timestamp":"2026-09-26T10:15:32Z","type":"PROCESS",
 "label":"powershell.exe spawned by cmd.exe (SYSTEM)","evidence_id":"uuid","severity":"HIGH" },
 { "timestamp":"2026-09-26T10:15:35Z","type":"FILE",
 "label":"C:\\Temp\\dropper.exe written","evidence_id":"uuid","severity":"CRITICAL" }] }

 GET /investigations/:id/graph — Evidence correlation graph (nodes + edges)

#### Response 200 (React Flow format)

```
{ "nodes":[{ "id":"proc_4567","type":"process","data":{"label":"powershell.exe","pid":4567} },
 { "id":"file_abc","type":"file","data":{"label":"dropper.exe","path":"C:\\Temp\\dropper.exe"} }],
 "edges":[{ "id":"e1","source":"proc_4567","target":"file_abc","label":"ACCESSED_FILE","type":"default" }] }

### AI Intelligence

 POST /investigations/:id/ai/correlate — Run AI correlation on all evidence

#### Response 202

```
{ "analysis_id":"uuid","status":"RUNNING","estimated_sec":30 }

 POST /investigations/:id/ai/query — RAG Q&A over collected evidence

#### Request

```
{ "question":"Which user account was compromised first?" }

#### Response 200

```
{ "answer":"Based on collected evidence, user 'svc_backup' (SID S-1-5-21-...) shows the earliest anomalous login at 10:12:44 UTC, 3 minutes before the suspicious process was spawned.",
 "evidence_refs":["uuid1","uuid2"],"confidence":0.87,"model":"claude-sonnet-4-6" }

### Reports

 POST /investigations/:id/reports — Generate investigation report

#### Request

```
{ "type":"FULL","title":"DataBreach-2026-09 Final Report" }

#### Response 202

```
{ "report_id":"uuid","status":"GENERATING","estimated_sec":60 }

 GET /investigations/:id/reports/:report_id/download — Download PDF report

#### Response
 Content-Type: application/pdf · Binary PDF stream

#### Auth
 All roles (AUDITOR gets read-only access)

## 07 Frontend Architecture

### Route Structure (Next.js App Router)

 RoutePage / PurposeAuthKey Components

 /loginLogin pagePublicLoginForm, JWT storage in httpOnly cookie

 /Redirect to /investigationsAuth—

 /investigationsInvestigation list + "New Investigation" CTAAuthInvestigationCard, StatusBadge, SearchFilter

 /investigations/newCreate investigation formINVESTIGATOR+InvestigationForm, TargetPicker

 /investigations/[id]Investigation overview: summary cards + recent activityAuthEvidenceSummaryCards, RecentJobsList, QuickFQL

 /investigations/[id]/fqlFQL Editor — write + execute forensic queriesINVESTIGATOR+FQLEditor (Monaco), PolicyPreview, JobStatusPanel, CollectorResultFeed

 /investigations/[id]/evidenceEvidence browser — table with filtersAuthEvidenceTable, EvidenceDetailDrawer, FilterBar, HashVerifyButton

 /investigations/[id]/timelineChronological timeline visualizationAuthD3Timeline, EventTooltip, TimeRangePicker, SeverityFilter

 /investigations/[id]/graphInteractive evidence correlation graphAuthReactFlowGraph, NodeDetailPanel, PathHighlighter, MITRETag

 /investigations/[id]/aiAI Intelligence — correlate + Q&AAuthCorrelateButton, WhatHappenedCard, EvidenceChatBox, ConfidenceIndicator

 /investigations/[id]/reportsReport generation + download historyAuthReportForm, ReportCard, DownloadButton, StatusTracker

 /admin/usersUser managementADMINUserTable, InviteUserModal, RolePicker

 /admin/policiesPolicy managementADMINPolicyEditor (YAML), PolicyTestModal

 /admin/auditAudit log viewerADMIN, AUDITORAuditTable, ActionFilter, ExportButton

### State Management

```
// Zustand store — global investigation state
interface InvestigationStore {
 currentInvestigationId: string | null;
 activeJobIds: string[]; // Jobs being polled
 wsConnected: boolean;
 setCurrentInvestigation: (id: string) => void;
 addActiveJob: (jobId: string) => void;
 removeActiveJob: (jobId: string) => void;
}

// React Query keys
const queryKeys = {
 investigations: ['investigations'],
 investigation: (id: string) => ['investigations', id],
 evidence: (id: string, filters: EvidenceFilters) => ['evidence', id, filters],
 timeline: (id: string, range: TimeRange) => ['timeline', id, range],
 graph: (id: string) => ['graph', id],
 jobStatus: (jobId: string) => ['jobs', jobId, 'status'],
}

### FQL Editor (Monaco)

```
// FQL Language Server features required:
// 1. Syntax highlighting (register custom language in Monaco)
// 2. Auto-complete: INVESTIGATE, WHERE, AND, OR, CONTAINS, IN, BETWEEN, TIMELINE FROM ... TO
// 3. Real-time validation: debounce 500ms, call POST /fql/validate
// 4. Policy preview panel: show ALLOWED/DENIED before execution
// 5. Keyboard shortcut: Ctrl+Enter to execute

// FQL Grammar (must match backend Lark grammar exactly):
// STATEMENT: "INVESTIGATE" COLLECTOR_TYPE ("WHERE" CONDITION ("AND"|"OR" CONDITION)*)?
// | "TIMELINE" "FROM" DATETIME "TO" DATETIME
// COLLECTOR_TYPE: "processes" | "files" | "network" | "users" | "events"
// CONDITION: FIELD OP VALUE
// OP: "=" | "!=" | "CONTAINS" | "IN" | ">" | " "2026-09-01"
// INVESTIGATE events WHERE type = "login_failure" AND count > 5
// TIMELINE FROM "2026-09-26T00:00" TO "2026-09-26T23:59"

### Key TypeScript Types

```
type UserRole = 'ADMIN' | 'LEAD_INVESTIGATOR' | 'INVESTIGATOR' | 'AUDITOR';
type InvestigationStatus = 'ACTIVE' | 'COMPLETED' | 'ARCHIVED' | 'SUSPENDED';
type EvidenceType = 'PROCESS' | 'FILE' | 'NETWORK_CONNECTION' | 'USER_ACCOUNT' | 'SYSTEM_EVENT' | 'TIMELINE_ENTRY' | 'PCAP_FILE' | 'LOG_ENTRY';
type CollectorType = 'PROCESS' | 'FILE' | 'NETWORK' | 'USER' | 'EVENT' | 'TIMELINE';
type JobStatus = 'PENDING' | 'VALIDATED' | 'POLICY_DENIED' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PARTIAL';

interface EvidenceItem {
 id: string; evidence_type: EvidenceType; collected_at: string;
 data: ProcessEvidence | FileEvidence | NetworkEvidence | UserEvidence | EventEvidence;
 data_hash: string; blockchain_status: 'NOT_SUBMITTED' | 'PENDING' | 'CONFIRMED' | 'FAILED';
 blockchain_tx?: string;
}

interface ProcessEvidence {
 pid: number; name: string; cmdline: string; user: string;
 parent_pid: number; parent_name: string; hash_sha256?: string;
 started_at: string; memory_mb?: number; cpu_percent?: number;
}

interface GraphData {
 nodes: GraphNode[]; edges: GraphEdge[];
}
interface GraphNode {
 id: string; type: 'process' | 'file' | 'network' | 'user' | 'event';
 data: { label: string; [key: string]: unknown }; position?: { x: number; y: number };
}
interface GraphEdge {
 id: string; source: string; target: string; label: string;
}

### WebSocket Integration

```
// Connect on investigation page mount, disconnect on unmount
const ws = new WebSocket(`wss://forgex.local/ws?token=${accessToken}&investigation_id=${id}`);

// Incoming message types:
// { type: 'JOB_STATUS', job_id: '...', status: 'RUNNING', progress: { completed: 1, total: 3 } }
// { type: 'JOB_COMPLETE', job_id: '...', evidence_count: 47 }
// { type: 'JOB_FAILED', job_id: '...', error: 'Collector timeout' }
// { type: 'AI_COMPLETE', analysis_id: '...' }

// On JOB_COMPLETE → invalidate evidence query, show toast notification

## 08 Backend Architecture

### Module Structure

```
forgex_backend/
├── main.py # FastAPI app factory, lifespan hooks
├── config.py # Settings (pydantic-settings, .env)
├── api/ # API layer — routers only, no business logic
│ ├── v1/
│ │ ├── auth.py
│ │ ├── investigations.py
│ │ ├── fql.py
│ │ ├── evidence.py
│ │ ├── ai_intelligence.py
│ │ ├── reports.py
│ │ ├── jobs.py
│ │ └── admin.py
├── core/ # Cross-cutting concerns
│ ├── auth.py # JWT creation/validation, RBAC decorator
│ ├── audit.py # Audit log writer
│ ├── exceptions.py # Domain exceptions → HTTP responses
│ └── websocket.py # WS connection manager
├── services/ # Business logic layer
│ ├── investigation_service.py
│ ├── fql_service.py # Parser + policy + orchestrator coordination
│ ├── evidence_service.py # Hash, store, embed
│ ├── ai_service.py # LLM calls, RAG, correlation
│ ├── report_service.py # PDF generation
│ └── blockchain_service.py # Evidence anchoring
├── fql/ # FQL subsystem
│ ├── grammar.lark # Lark EBNF grammar file
│ ├── parser.py # FQL → AST
│ ├── ast_types.py # Dataclasses for AST nodes
│ └── to_collector_params.py # AST → collector params dict
├── policy/
│ ├── engine.py # Policy evaluation
│ ├── loader.py # Load policies from DB/cache
│ └── models.py # Policy dataclasses
├── collectors/ # Forensic collection modules
│ ├── base.py # Abstract BaseCollector
│ ├── process_collector.py # psutil-based
│ ├── file_collector.py # os.walk based
│ ├── network_collector.py # PCAP/Zeek
│ ├── user_collector.py # pwd/grp (Linux), SAM (Windows)
│ ├── event_collector.py # evtx / syslog / auditd
│ └── timeline_builder.py # Merges all evidence into timeline
├── workers/ # Celery tasks
│ ├── celery_app.py
│ ├── collector_tasks.py
│ ├── ai_tasks.py
│ └── report_tasks.py
├── db/
│ ├── session.py # SQLAlchemy async engine
│ ├── models.py # ORM models (match schema above)
│ └── neo4j_client.py # Neo4j async driver
├── repositories/ # Data access layer
│ ├── investigation_repo.py
│ ├── evidence_repo.py
│ ├── user_repo.py
│ └── audit_repo.py
└── schemas/ # Pydantic request/response models
 ├── auth.py
 ├── investigation.py
 ├── fql.py
 ├── evidence.py
 └── ai.py

### FQL Grammar (Lark EBNF)

```
// file: forgex_backend/fql/grammar.lark
start: statement

statement: investigate_stmt | timeline_stmt

investigate_stmt: "INVESTIGATE" COLLECTOR ("WHERE" condition (BOOL_OP condition)*)?
timeline_stmt: "TIMELINE" "FROM" DATETIME "TO" DATETIME

COLLECTOR: "processes" | "files" | "network" | "users" | "events"
BOOL_OP: "AND" | "OR"

condition: FIELD OP value
OP: "=" | "!=" | "CONTAINS" | "NOT CONTAINS" | "IN" | "NOT IN" | ">" | "=" | "

### Policy Engine Rules (YAML format stored in DB)

```
name: default-investigation-policy
allowed_collectors:
 - processes
 - files
 - users
 - events
 - timeline
restricted_collectors:
 network:
 required_role: LEAD_INVESTIGATOR
 requires_case_status: ACTIVE
 max_capture_duration_sec: 300
 log_mandatory: true
field_restrictions:
 files:
 excluded_paths:
 - "/proc"
 - "/sys"
 - "C:\\Windows\\System32" # requires elevated permission flag
 max_depth: 8
rate_limits:
 max_executions_per_hour_per_investigator: 20
 max_concurrent_jobs: 3

### Layer Responsibilities — Business Logic Rules

 LayerWhat lives hereWhat does NOT belong here

 API RouterHTTP validation (Pydantic), auth middleware, response serializationBusiness logic, DB calls

 ServiceOrchestration: call parser → call policy → enqueue job → call repo to saveRaw SQL, HTTP request parsing

 RepositorySQLAlchemy queries, Neo4j Cypher execution, caching logicBusiness decisions

 CollectorOS-level forensic data collection, raw data returned as dictHashing, storing — pass raw data back to service

 Worker (Celery)Job coordination, timeout handling, retries, calling collectorsBusiness logic beyond what's in services

### Async Operations

- FQL execution → always async (Celery job). API returns 202 immediately with job_id.

- AI correlation → always async (Celery job, up to 60s).

- Report generation → always async (Celery job, up to 120s).

- Blockchain anchoring → async fire-and-forget per evidence item, best-effort.

- pgvector embedding → background task after evidence saved.

## 09 AI Architecture

### Provider Abstraction

```
class LLMProvider(Protocol):
 async def complete(self, messages: list[Message], response_format: type[BaseModel]) -> BaseModel: ...

class AnthropicProvider:
 model = "claude-sonnet-4-6"
 async def complete(self, messages, response_format): ...

class OpenAIProvider:
 model = "gpt-4o"
 async def complete(self, messages, response_format): ...

# In config:
PRIMARY_LLM = AnthropicProvider()
FALLBACK_LLM = OpenAIProvider()

async def llm_complete(messages, response_format):
 try:
 return await PRIMARY_LLM.complete(messages, response_format)
 except (TimeoutError, RateLimitError):
 await asyncio.sleep(2)
 return await FALLBACK_LLM.complete(messages, response_format) # one fallback

### Prompt Architecture

#### Correlation Prompt (What Happened?)

```
SYSTEM = """You are a digital forensics AI assistant. You analyze collected forensic evidence
and produce structured incident reconstructions. You ONLY reason about evidence explicitly
provided. You do NOT speculate beyond the data. Every claim MUST cite an evidence_id.
Output ONLY valid JSON matching the schema below. No prose outside the JSON."""

USER = """Investigation: {investigation_name}
Target: {target_host} ({target_os})

EVIDENCE:
{evidence_json} ← top 50 items ranked by relevance (RAG)

CORRELATION GRAPH SUMMARY:
{graph_summary}

Produce a CorrelationResult JSON:
{
 "what_happened": "string — concise narrative of the incident",
 "attack_stages": [{"stage":"string","description":"string","evidence_ids":["uuid"]}],
 "suspicious_indicators": [{"indicator":"string","severity":"HIGH|MED|LOW","evidence_ids":["uuid"]}],
 "mitre_techniques": [{"technique_id":"T1059.001","name":"PowerShell","evidence_ids":["uuid"]}],
 "confidence": 0.0-1.0,
 "gaps": ["string — what evidence is missing to complete the picture"]
}"""

#### RAG Q&A Prompt

```
SYSTEM = """You are a forensic evidence analyst. You answer investigator questions strictly
based on the collected evidence provided. Cite evidence_ids for every factual claim.
If the evidence does not contain the answer, say so explicitly — do not guess."""

USER = """Question: {investigator_question}

Relevant Evidence (retrieved via semantic search):
{rag_evidence_chunks}

Answer in JSON: {"answer": "string", "evidence_refs": ["uuid"], "confidence": 0.0-1.0,
"caveat": "string or null"}"

### RAG Pipeline

```
async def retrieve_relevant_evidence(query: str, investigation_id: str, top_k: int = 20) -> list[EvidenceItem]:
 # 1. Embed the query
 query_embedding = await embed_text(query) # text-embedding-3-small, 1536 dims

 # 2. Vector similarity search in pgvector (cosine distance)
 sql = """
 SELECT ei.*, 1 - (ee.embedding $1) AS similarity
 FROM evidence_embeddings ee
 JOIN evidence_items ei ON ei.id = ee.evidence_id
 WHERE ei.investigation_id = $2
 ORDER BY similarity DESC
 LIMIT $3
 """
 results = await db.fetch(sql, query_embedding, investigation_id, top_k)

 # 3. Filter by similarity threshold (> 0.3)
 return [r for r in results if r.similarity > 0.3]

### Evidence Embedding Strategy

Each evidence item is converted to a human-readable text representation for embedding:

```
def evidence_to_text(item: EvidenceItem) -> str:
 if item.evidence_type == "PROCESS":
 d = item.data
 return f"Process '{d['name']}' (PID {d['pid']}) run by user '{d['user']}', command: {d['cmdline']}, parent: '{d['parent_name']}' at {item.collected_at}"
 elif item.evidence_type == "FILE":
 d = item.data
 return f"File '{d['path']}' (size {d['size']} bytes), SHA256: {d.get('hash_sha256','unknown')}, modified: {d.get('modified_at')}"
 elif item.evidence_type == "NETWORK_CONNECTION":
 d = item.data
 return f"Network connection from {d['src_ip']}:{d['src_port']} to {d['dst_ip']}:{d['dst_port']} ({d['protocol']}) at {item.collected_at}"
 # ... etc

### Hallucination Controls

- Output validated against strict Pydantic JSON schema before storage. If invalid → discard result, return error to user.

- Every claim in correlation result includes evidence_ids. Frontend verifies IDs exist in evidence table before displaying.

- System prompt explicitly forbids speculation beyond provided evidence.

- Confidence < 0.4 triggers "LOW CONFIDENCE" warning banner in UI.

- Prompt injection defense: evidence content is escaped and wrapped in XML tags <evidence>...</evidence>; any instruction-like content inside is neutralized.

### Blockchain Evidence Anchoring

```
async def anchor_evidence_hash(evidence_id: str, data_hash: str) -> Optional[str]:
 """Submit evidence hash to Ethereum Sepolia testnet for immutable proof."""
 # 1. Build Ethereum transaction with data = keccak256(evidence_id + data_hash + timestamp)
 # 2. Sign with FORGE-X wallet private key (never exposed to users)
 # 3. Submit to Sepolia via web3.py
 # 4. Store tx_hash in evidence_items.blockchain_tx
 # 5. Background: poll for confirmation (10 blocks) → update blockchain_status to CONFIRMED

 payload = keccak256(f"{evidence_id}:{data_hash}:{datetime.utcnow().isoformat()}")
 tx_hash = await w3.eth.send_raw_transaction(signed_tx.rawTransaction)
 return tx_hash.hex()

## 10 Security Architecture

 ThreatVectorMitigation

 Authentication bypassInvalid/expired JWT acceptedValidate signature + expiry on every request. Revoke tokens by storing jti in Redis deny-list on logout.

 IDORGET /investigations/other-users-idEvery query scopes to created_by = current_user.id OR user has LEAD/ADMIN role. No raw UUID lookup without ownership check.

 Broken RBACINVESTIGATOR runs network capture (LEAD required)Policy engine enforced server-side. Role check on every collector type. Test: unit test all role/collector combinations.

 FQL InjectionMalicious FQL trying to exec OS commandsFQL parser is grammar-based (Lark). If it's not valid grammar, it's rejected. FQL→collector params are typed dicts — no shell interpolation, no eval().

 Path traversal in file collectorFQL: INVESTIGATE files WHERE path = "/etc/shadow"Policy engine has excluded_paths list. File collector validates all resolved paths are within allowed prefixes before reading.

 SSRFtarget_host set to internal metadata URLValidate target_host is a legitimate RFC-1918 or DNS name. Block AWS metadata IPs (169.254.x.x), loopback, and non-routable ranges unless explicitly whitelisted.

 Prompt InjectionEvidence payload contains malicious instructions to LLMEvidence content is XML-escaped and wrapped in <evidence> tags with explicit system instructions that treat inner content as data only.

 Evidence tamperingDB admin modifies stored evidenceSHA-256 hash stored at collection time. Frontend verifies hash on display. Blockchain anchor provides external immutability proof.

 Secret leakageLLM API keys in frontend or logsAPI keys stored only in backend .env (Docker secrets in production). Never returned in API responses. Audit logs scrubbed of secrets.

 API abuse / DoSRapid FQL execution floods collectorsRate limiting: 20 FQL executions/hour/investigator (Redis counter). Max 3 concurrent jobs per investigation. Nginx rate limits: 100 req/min/IP.

 XSSInvestigator name/evidence data rendered as HTMLNext.js escapes by default. Evidence data always rendered as text, never dangerouslySetInnerHTML. CSP header: default-src 'self'.

 CSRFCross-site form submissionJWT in httpOnly cookies + double-submit CSRF token for state-changing requests. CORS restricted to known origin.

 Unsafe file uploadPCAP files with malicious contentPCAP files stored by hash-based filename in isolated directory. Never executed. Zeek processes in sandboxed subprocess with timeout.

 Sensitive data in logsEvidence data or JWT in app logsStructured logging with field masking. Log level INFO in production — no DEBUG (avoids logging request bodies).

 Collector privilege escalationCollector runs as root and is abusedCollectors run as a dedicated forgex-collector user with minimal Linux capabilities (CAP_NET_RAW for PCAP only, dropped after use). No setuid.

### Security Headers (Nginx)

```
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

## 11 Scalability Plan

### Current Limits (MVP — Single Docker Compose)

 DimensionMVP CapacityBottleneckScaling Path

 Concurrent investigations~10 activeNeo4j community (single writer)Neo4j Enterprise or partition by investigation

 Evidence items~500K rowspgvector index rebuildTimescaleDB partitioning by collected_at

 Concurrent Celery workers4 (default)Memory / CPU on hostAdd worker nodes; horizontal Celery scale

 LLM throughput~5 concurrent AI jobsAPI rate limits (Anthropic/OpenAI)Request queue + retry with backoff; multi-key pool

 File storage (PCAP)Local diskDisk sizeMinIO / S3-compatible object storage

 WebSocket connections~50Single FastAPI instanceRedis pub/sub fan-out to multiple instances

### Caching Strategy

- Policies: Cached in Redis for 60s (TTL). Invalidated on policy update.

- Investigation summary stats: Cached 30s in Redis. Invalidated on new evidence.

- Evidence graph: Cached in Redis 5min per investigation. Invalidated on new evidence.

- LLM responses: NOT cached — always re-generate on request (evidence may have changed).

- Report PDFs: Stored permanently in file store; link served from DB.

## 12 Testing Strategy

 Test TypeToolCoverage TargetsPriority

 Unit — FQL ParserpytestAll valid statements; all error cases with correct line/col🔴 CRITICAL

 Unit — Policy EnginepytestAll role/collector combinations; rate limit logic🔴 CRITICAL

 Unit — Evidence ServicepytestSHA-256 hash correctness; UNIQUE constraint enforcement🔴 CRITICAL

 Unit — Collectorspytest + mocksMocked OS calls; correct data schema returned🟡 HIGH

 Unit — AI Output ValidationpytestValid JSON → accepted; invalid JSON → discarded; hallucination of fake IDs → caught🔴 CRITICAL

 Integration — APIpytest + httpxAll endpoints; auth enforcement; RBAC; error responses🔴 CRITICAL

 Integration — DBpytest + test DBEvidence immutability; audit log writes; cascade deletes🟡 HIGH

 Integration — FQL → EvidencepytestEnd-to-end: FQL → policy → collector → evidence stored correctly🔴 CRITICAL

 Security — RBACpytestEvery endpoint with every role combination🔴 CRITICAL

 Security — FQL InjectionpytestMalicious FQL inputs; path traversal attempts; oversized inputs🔴 CRITICAL

 E2E — Core FlowsPlaywrightLogin → create investigation → write FQL → view evidence → view graph🟡 HIGH

 Frontend — ComponentsVitest + Testing LibraryFQLEditor, EvidenceTable, Timeline, Graph🟢 MED

 PerformanceLocust100 concurrent users; FQL execution p95 < 30s🟢 MED

## 13 MVP Scope

 MVP Definition: A running FORGE-X instance that can accept FQL queries, collect forensic data from a local Linux/Windows system, store evidence with hashes, correlate via Neo4j, provide LLM-powered "What Happened?" output, display an interactive timeline and graph, and generate a PDF report. All in a single docker compose up.

### MVP Feature Set

 #FeatureIn MVP

 1JWT auth + 4 roles✅

 2FQL editor (Monaco) with syntax highlighting✅

 3FQL parser (processes, files, users, events, timeline)✅

 4Policy engine (YAML rules, RBAC on collectors)✅

 5Process collector (psutil, cross-platform)✅

 6File collector (os.walk, metadata + hash)✅

 7User account collector✅

 8System event collector (Linux syslog / Windows evtx)✅

 9Network collector — active connections (psutil)✅

 10PCAP capture (requires LEAD role)⚡ Demo only

 11SHA-256 hashing of all evidence✅

 12PostgreSQL evidence storage✅

 13Neo4j correlation graph✅

 14D3 timeline visualization✅

 15React Flow evidence graph✅

 16LLM "What Happened?" correlation✅

 17RAG evidence Q&A✅

 18PDF report generation✅

 19Full audit log✅

 20Blockchain hash anchoring (Sepolia)⚡ Demo only

 21MITRE ATT&CK mapping in AI output✅ (in LLM prompt)

 22WebSocket live job status✅

 23Docker Compose single-command deploy✅

## 14 Implementation Roadmap

### Phase A — Foundation (Days 1-2)

 IDTaskOwnerAcceptance Criteria

 A1Docker Compose file with FastAPI, Postgres, Neo4j, Redis, NginxOpenCodedocker compose up → all services healthy

 A2PostgreSQL schema migrations (Alembic)OpenCodeAll tables created; indexes in place

 A3Neo4j schema + constraints + test connectionOpenCodeNeo4j reachable; constraints applied

 A4FastAPI app skeleton with CORS, middleware, health endpointOpenCodeGET /health → 200

 A5Next.js project with Tailwind, shadcn/ui, auth skeletonCursorNext.js dev server runs; login route visible

### Phase B — Backend Core (Days 2-4)

 IDTaskDependenciesAcceptance Criteria

 B1Auth service: JWT issuance, refresh, RBAC middlewareA2POST /auth/login returns valid JWT; middleware blocks unauthenticated requests

 B2FQL parser (Lark grammar)A4All valid FQL examples parsed; invalid FQL returns line/col error

 B3Policy engine (YAML loader + evaluator)A2, B2Role/collector matrix passes all unit tests

 B4Process collector (psutil)A4Returns list of running processes with pid, name, user, cmdline, hash

 B5File collectorA4Returns file metadata + SHA-256 for given path

 B6User + Event collectorsA4Returns user accounts and last N system events

 B7Network collector (active connections via psutil)A4Returns active TCP/UDP connections with process association

 B8Evidence service (hash + PostgreSQL + Neo4j)A2, A3Evidence item saved; hash verified; Neo4j node created

 B9Forensic Orchestrator + Celery workersB2,B3,B4-B7,B8FQL execute → job queued → collectors run → evidence saved

 B10Audit logger (all API mutations)A2Every state-changing call produces audit_log row

 B11WebSocket job status hubB9Browser receives JOB_COMPLETE within 2s of Celery task completion

### Phase C — Frontend Core (Days 3-5)

 IDTaskDependenciesAcceptance Criteria

 C1Auth: login page, JWT storage, protected routesB1, A5Login → redirect to /investigations; logout clears token

 C2Investigation list + create flowC1Create investigation → appears in list

 C3FQL Editor (Monaco) with syntax highlight + validationC1, B2Invalid FQL shows error with line number; valid FQL shows policy preview

 C4FQL execute → job status → evidence feed (WebSocket)C3, B9, B11Execute FQL → spinner → "47 evidence items collected" toast

 C5Evidence browser table with filtersC4Table shows all evidence; filter by type/time works; hash visible

 C6D3 Timeline visualizationC4Chronological events visible; hover shows detail

 C7React Flow evidence graphC4Nodes and edges render; click node shows detail; pan/zoom works

### Phase D — AI + Reports (Days 5-7)

 IDTaskDependenciesAcceptance Criteria

 D1pgvector embedding pipeline (evidence indexing)B8Evidence items embedded after collection; similarity search returns relevant results

 D2LLM correlation service (What Happened?)D1AI correlation returns structured JSON; confidence score displayed; evidence refs verified

 D3RAG Q&A endpoint + UID1Ask "which user was compromised?" → answer cites evidence_ids

 D4PDF report generation (WeasyPrint)D2Generate report → downloadable PDF with timeline, evidence table, AI narrative

 D5Blockchain anchoring (Sepolia)B8evidence_items.blockchain_tx populated; Etherscan link shows tx with correct hash

### Phase E — Security + Testing (Days 7-8)

 IDTaskAcceptance Criteria

 E1RBAC enforcement tests (all role/endpoint combinations)Zero unauthorized access in test matrix

 E2FQL injection testsAll malicious inputs rejected by parser; no shell execution

 E3Evidence integrity test (hash verification)Modified evidence detected; UI shows "TAMPERED" badge

 E4Rate limiting test21st FQL execution returns 429

 E5Security headers audit (Codex)All headers present; CSP passes; no secrets in responses

### Phase F — Demo Readiness (Day 8-9)

 IDTaskAcceptance Criteria

 F1Seeded demo investigation with realistic evidenceDemo loads in 2s; shows populated timeline and graph

 F2FORGE-X Logo / branding in UIProfessional appearance; no placeholder text

 F3docker compose up → fully working system in <2 minSingle command demo for SIH judges

 F4README with architecture overview + demo scriptJudges can run and understand the demo independently

## 15 Cursor Frontend Handoff

Cursor: Implement the Next.js frontend using this specification exactly. Do not invent API contracts — all endpoints are defined in §06.

#### Stack

```
Next.js 15 (App Router) · TypeScript 5.x · Tailwind CSS 3.x · shadcn/ui
Zustand (global state) · @tanstack/react-query v5 (server state)
Monaco Editor (FQL editing) · React Flow v12 (evidence graph) · D3.js v7 (timeline)
Recharts (evidence summary charts) · react-pdf (report preview)
axios (API client, interceptors for JWT refresh) · date-fns (timestamps)

#### Environment Variables

```
NEXT_PUBLIC_API_URL=https://forgex.local/api/v1
NEXT_PUBLIC_WS_URL=wss://forgex.local/ws

#### Auth Pattern

- Access token: store in Zustand memory (NOT localStorage). Lost on page refresh → handled by refresh token.

- Refresh token: httpOnly cookie set by backend (not accessible to JS).

- On 401 from any API call → call POST /auth/refresh → retry original request. If refresh fails → redirect to /login.

- All protected routes: use Next.js middleware to check for valid session.

#### Critical UX Requirements

- FQL Editor must show real-time validation (debounce 500ms). Show policy preview before execution.

- Job execution must use WebSocket for live status — do NOT poll every second.

- Evidence table must support virtual scrolling (10K+ rows possible). Use TanStack Virtual.

- Graph view: nodes color-coded by type (process=blue, file=green, network=orange, user=purple, event=red).

- Timeline: click event → highlight corresponding node in evidence table and graph (cross-highlight).

- Hash value display: show first 12 chars + copy button. Full hash in tooltip.

- Blockchain status: show colored badge (grey=not submitted, yellow=pending, green=confirmed).

- All loading states: use skeleton cards, not spinners (more professional for forensic tool).

- Empty states: always explain why empty and suggest next action (e.g., "No evidence yet — write a FQL query to start collecting").

- Accessibility: all interactive elements keyboard-navigable; WCAG 2.1 AA minimum.

#### Acceptance Criteria for Cursor

- Login flow works end-to-end with real backend JWT

- FQL Editor has syntax highlighting for the FQL grammar defined in §07

- FQL validation shows line/column error correctly

- Execute FQL → WebSocket updates job status in real time

- Evidence table loads 1000+ items without freezing (virtual scroll)

- Timeline renders all events chronologically with severity color coding

- Graph shows USER→PROCESS→FILE→NETWORK→EVENT relationships with correct node types

- AI "What Happened?" result shows confidence, evidence refs, and MITRE tags

- Report download works (PDF binary stream from API)

- All TypeScript types in §07 used — no any except in third-party adapter code

- Responsive: usable on 1280px minimum width (forensic analyst desktop)

## 16 OpenCode Backend Handoff

OpenCode: Implement the Python FastAPI backend using this specification exactly. Match all API response shapes defined in §06 precisely — Cursor will type-check against them.

#### Stack

```
Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 (async) · Alembic · asyncpg
Celery 5.4 · Redis (celery broker) · neo4j (official async driver)
Lark 1.2 (FQL parser) · psutil · pyshark (PCAP) · python-evtx
weasyprint (PDF) · web3.py (blockchain) · anthropic SDK · openai SDK
passlib[bcrypt] · PyJWT · pydantic-settings · structlog

#### Critical Implementation Rules

- FQL parser MUST use the Lark grammar in §08 exactly. Do not write a custom regex parser.

- Policy engine MUST be evaluated BEFORE any collector is called. Policy check cannot be bypassed.

- Evidence hash (SHA-256) MUST be computed of json.dumps(data, sort_keys=True).encode('utf-8') BEFORE the DB write.

- Audit log MUST be written synchronously in the same transaction as the action it audits.

- LLM API keys MUST only be in .env / Docker secrets. Never returned in any API response.

- AI output MUST be validated against Pydantic schema before storage. Invalid output is discarded — do NOT store it.

- All collector sub-processes MUST have a 30-second timeout enforced by asyncio.wait_for().

- Celery tasks must use acknowledge late=True and reject on worker lost for evidence collection tasks.

#### Collector Output Schema (must match frontend types)

```
ProcessEvidence(TypedDict):
 pid: int; name: str; cmdline: str; user: str;
 parent_pid: int; parent_name: str; hash_sha256: Optional[str]
 started_at: str; memory_mb: Optional[float]; cpu_percent: Optional[float]

FileEvidence(TypedDict):
 path: str; size: int; hash_sha256: str; hash_md5: str
 created_at: str; modified_at: str; accessed_at: str
 permissions: str; owner: str; is_executable: bool

NetworkConnectionEvidence(TypedDict):
 src_ip: str; src_port: int; dst_ip: str; dst_port: int
 protocol: str; state: str; pid: Optional[int]; process_name: Optional[str]
 bytes_sent: Optional[int]; bytes_recv: Optional[int]

UserEvidence(TypedDict):
 username: str; uid: Optional[int]; gid: Optional[int]; home: str
 shell: str; last_login: Optional[str]; groups: list[str]

SystemEventEvidence(TypedDict):
 event_id: Optional[int]; event_type: str; timestamp: str
 source: str; description: str; user: Optional[str]; pid: Optional[int]

#### Acceptance Criteria for OpenCode

- docker compose up → all services healthy within 60s

- POST /auth/login returns JWT with correct role claim

- FQL "INVESTIGATE processes WHERE name CONTAINS 'python'" collects real processes

- Evidence items have valid SHA-256 hash; hash verified on GET

- Neo4j graph shows correct relationships after evidence collection

- Policy engine denies network capture for INVESTIGATOR role

- Audit log has entry for every investigation creation and FQL execution

- AI correlation returns valid JSON matching CorrelationResult schema

- Invalid LLM output discarded; endpoint returns error — not garbage data

- Rate limit: 21st FQL execution in an hour returns HTTP 429

- All endpoints return errors in standard format defined in §06

- Alembic migrate from scratch reproduces full schema

## 17 Risks

 RiskLikelihoodImpactMitigation

 LLM API unavailable or rate-limited during demoHIGHHIGH — "What Happened?" feature breaksPre-generate and cache a demo AI response; show cached result if API fails. Fallback to OpenAI if Anthropic fails.

 Neo4j complexity underestimated; graph queries slowMEDMED — correlation dashboard sluggishLimit graph to top 200 nodes per investigation in MVP. Add LIMIT to all Cypher queries.

 PCAP capture requires root / CAP_NET_RAWHIGHMED — network collector needs privilege setupDocument setup clearly. For demo: use pre-captured .pcap file for Zeek analysis instead of live capture.

 WeasyPrint PDF rendering breaks on complex HTMLMEDLOW — report feature onlyTest report template early (Phase D4). Keep template simple: tables and lists only, no complex CSS.

 Blockchain Sepolia testnet congested; anchor failsMEDLOW — demo feature onlyBlockchain anchor is async fire-and-forget. Demo shows status="PENDING" which is acceptable for judges.

 FQL grammar too limited for demo scenarioLOWHIGH if judges ask unsupported queriesPre-plan 5 specific demo FQL queries. Rehearse them. Add those specific capabilities first.

 Windows collector untested (team likely on Linux)HIGHMED — demo on Linux covers thisDemo on Linux only. Document Windows support as roadmap item. Use psutil cross-platform functions only.

## 18 Definition of Done

The product is DONE when ALL of the following are true:

### Backend

- All API endpoints in §06 implemented and returning correct response shapes

- FQL parser handles all 5 collector types with WHERE clauses

- Policy engine enforces all role/collector restrictions

- All 5 collectors (process, file, network, user, event) operational on Linux

- Every evidence item has SHA-256 hash; constraint prevents duplicates

- Neo4j receives evidence nodes and relationships after every collection

- AI correlation returns structured JSON with evidence citations

- PDF report generated with timeline + evidence table + AI narrative

- Audit log written for every state-changing action

- Rate limiting enforced (429 on excess)

- All unit tests pass (parser, policy, evidence service, AI validation)

- All API integration tests pass

- No Python security warnings from bandit scan

### Frontend

- Login, investigation creation, FQL execution, evidence browse, timeline, graph, AI, reports — all functional

- FQL editor validates syntax in real time

- WebSocket delivers live job status updates

- Evidence graph renders USER→PROCESS→FILE→NETWORK→EVENT correctly

- Timeline is chronological; events clickable

- AI result page shows "What Happened?" narrative with MITRE tags

- No TypeScript errors (tsc --noEmit passes)

- No accessibility violations (axe-core scan)

### Infrastructure

- docker compose up → fully working system within 90 seconds

- TLS configured for local HTTPS (self-signed for dev, documented for prod)

- All secrets in .env; .env.example committed without real secrets

- Database migrations reproducible from scratch

- README contains architecture overview + demo script with exact FQL queries to type

### Security

- All security headers present (validated by securityheaders.com or equivalent)

- No API keys or passwords in any log output

- RBAC test matrix: all role/endpoint combinations documented and tested

- FQL injection test suite passes

- Evidence hash verified by Codex audit

### Demo Readiness

- Demo investigation pre-seeded with realistic evidence (minimum 50 items across all types)

- AI "What Happened?" pre-cached response available if API is down

- Blockchain anchor tx visible on Sepolia Etherscan for at least one evidence item

- 5-minute demo script rehearsed end-to-end by at least 2 team members

- Architecture diagram printed or on second screen for judge Q&A

