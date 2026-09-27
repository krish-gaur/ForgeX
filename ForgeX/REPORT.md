# FORGE·X — Implementation Report

**Team AIGloryThm · Smart India Hackathon 2026 · Problem SIH26148**
*Creation of scripts/functions with new programming language to commence
Computer & Network forensic analysis without triggering security solutions.*
**Sponsoring organisation:** NTRO · **Theme:** Blockchain & Cybersecurity · **Category:** Software

---

## 1. Structure

```
ForgeX/                                  (~13,500 lines incl. tests & UI)
├── backend/
│   ├── app/
│   │   ├── api/v1/            10 routers · 48 HTTP handlers · /api/v1 prefix
│   │   ├── core/              security (JWT+bcrypt), RBAC, errors, audit chain, WS hub
│   │   ├── db/                SQLAlchemy models, async session, Alembic env
│   │   ├── fql/               FQL: Lark grammar, parser, AST, planner, validators
│   │   ├── collectors/        processes · files · network · users · events · timeline
│   │   ├── execution/         sandbox: child runner, import blocker, resource caps
│   │   ├── policy/            YAML policy loader + pre-execution enforcement gate
│   │   ├── services/          pipeline runners, evidence, graph, reports, anchoring, RAG
│   │   ├── ai/                correlation (LLM|heuristic), embeddings, Q&A, promotion
│   │   ├── graph/             GraphStore interface: SQL (default) · Neo4j (optional)
│   │   ├── jobs/              executor: inline asyncio (default) · Celery (optional)
│   │   ├── schemas/           Pydantic request/response contracts
│   │   ├── config.py          pydantic-settings (.env driven)
│   │   └── main.py            app factory, middleware, mounts, /ws endpoint, /health
│   ├── forgex_sdk/forgex/     the `forgex` SDK (417 lines) + `_runtime` child entry
│   ├── templates/functions/   10 forensic function templates (505 lines)
│   ├── alembic/versions/      1 migration, 18 tables
│   ├── tests/                 72 tests (847 lines) across 10 files
│   └── requirements{,-extra}.txt, pytest.ini, ruff.toml, .env.example
├── frontend/                  15 routes (4,813 lines)
│   ├── app/                   login · dashboard · cases (+8 case sub-pages)
│   │                           templates · audit · settings
│   ├── components/            Shell (nav+RBAC), Monaco, FQL console, UI kit
│   └── lib/                   typed API client, auth, WS, data hooks, formatters
├── datasets/                  synthetic forensic samples (SYNTHETIC-labeled)
├── docs/                      ARCHITECTURE.md · ASSUMPTIONS.md
├── infrastructure/
│   ├── docker/                Dockerfile.backend · Dockerfile.frontend · compose
│   └── nginx/                 forgex.conf (API/WS/UI routing, TLS-ready)
├── scripts/                   run_local.sh · smoke_api.py
└── README.md · REPORT.md
```

## 2. Technology stack

| Layer | Choice | Version / notes |
|---|---|---|
| Backend framework | FastAPI | 0.115.6, async throughout |
| ASGI server | uvicorn | 0.34.0 (WebSocket native) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | 2.0.36 / 1.14.0 |
| Database | SQLite (aiosqlite) default → PostgreSQL (asyncpg) | zero-setup → production |
| DSL engine | Lark (Earley parser) | 1.2.2 — FQL grammar → AST → planner |
| Sandbox | CPython subprocess + `sys.meta_path` blocker + `resource` RLIMITs | stdlib only |
| Hashing / custody | hashlib SHA-256 (stdlib) | pre-DB hashing, append-only chain |
| Reports | reportlab | 4.2.5 (PDF: FULL / SUMMARY / CHAIN_OF_CUSTODY) |
| Auth | PyJWT + bcrypt | HS256, access + refresh cookie, rate-limited login |
| Live updates | WebSockets | `/ws?token=…&investigation_id=…` |
| Optional (lazy) | PostgreSQL · Neo4j · Celery/Redis · web3 (Sepolia) · Anthropic · OpenAI | `requirements-extra.txt`, all behind interfaces |
| Frontend | Next.js 15 (App Router) + React 19 + TypeScript | 15.5.26 |
| Editor | Monaco | 4.7.0 (YAML policy authoring + Python forensic functions) |
| Graph viz | @xyflow/react | 12.4.2, custom node type, deterministic layered layout |
| Timeline | hand-rolled SVG | no chart dependency, full control |
| Styling | Tailwind CSS | custom dark security-lab design system |

## 3. Features (all functional — no placeholders)

**FQL — the new forensic language.** `collect <collector> [where <predicate>]
[last <window>] [limit <n>]` compiles through a real grammar to collector plans.
`POST /fql/validate` returns the parsed AST, estimated collectors and the policy
verdict **without executing**; `POST /fql/execute` returns `202` with a job id and
a status endpoint.

**Controlled execution pipeline.** Validation → policy gate → sandbox → execution
→ artifact processing → findings → evidence → audit → report. Each stage is a
real, tested component; failures surface as typed errors in the standard envelope.

**Sandbox.** Forensic functions run in a separate OS process with a meta-path
import blocker, a replaced `__import__` (so the `sys.modules` cache cannot bypass
it), a filtered builtins set, CPU/AS RLIMITs, wall-clock timeout, and untrusted
output handling — SIGXCPU/SIGKILL and empty/garbage stdout all produce proper
FAILED jobs, never fabricated successes.

**Policy engine.** YAML policies: `allowed_collectors`, `restricted_collectors`
(per-collector `required_role`, `requires_case_status`, `max_capture_duration_sec`,
`log_mandatory`), `field_restrictions` (`excluded_paths`, `max_depth`,
`max_file_bytes`), and `rate_limits`. Enforced server-side before every run; the
same policy drives the validate-time preview. Authors can write/validate policies
in Monaco from the Settings page.

**Template-first Script Lab.** 10 templates — Windows Event, Registry, File
Metadata, Network Artifact, Process, Memory, Browser Artifact, Timeline
Generation, Hash Verification, Custom. Each ships with imports, function
structure, parameters, expected output, error handling, forensic context, inline
docs and examples. The empty editor is not a reachable state.

**Evidence & chain of custody.** SHA-256 computed before persistence, integrity
re-verification on demand, `AnchorLedger` interface (local hash chain default;
Sepolia testnet optional), CSV/JSON export.

**AI (evidence-first).** Correlation produces `what_happened`, `attack_stages`,
`suspicious_indicators` (each with real `evidence_ids`), `mitre_techniques`,
`gaps`, `confidence` and an explicit caveat. Provider chain Anthropic → OpenAI →
deterministic heuristic engine that cites real evidence. Q&A answers with
evidence references. AI indicators can be promoted to findings, carrying their
evidence ids.

**RBAC + audit.** Four roles with server-enforced permissions; append-only audit
log (written in the same transaction as the audited change) with actor, action,
target, metadata, filters and CSV export.

**Visualization.** Custom SVG timeline lane chart (severity/type colored, hover,
click-synced with the event log) and the correlation graph (users → processes →
files/network → events) with node inspector, minimap and controls.

**Reports.** FULL / SUMMARY / CHAIN_OF_CUSTODY PDFs generated server-side, with
async job polling and download.

**Demo mode.** Deterministic `DEMO-Corp-Breach-2026` case, every artifact labeled
**SYNTHETIC** in provenance, UI, and exported reports.

**Real error states.** All ten required states are implemented and surfaced with
actionable messages: Invalid Script, Execution Timeout, Unsupported Artifact,
Permission Denied, Evidence Unavailable, Parser Error, Sandbox Violation, Invalid
Template, AI Processing Failure, Database Failure.

## 4. Key decisions

1. **Runnable-first dependency strategy.** Anything not guaranteed to exist in the
   evaluation environment (Postgres, Redis, Neo4j, LLM keys, testnet funds) is
   optional and behind an interface with a working default. No feature is a stub:
   the optional implementations are complete.
2. **Two language layers, one engine.** FQL is the genuinely new intent language;
   the hardened Python subset + `forgex` SDK provides forensic depth. Both compile
   to the same six collectors, so there is exactly one execution path to audit and
   test.
3. **Evidence-first AI.** Output shape is fixed regardless of provider; the
   heuristic engine emits the same structure as the LLM path, always citing real
   `evidence_id`s and stating its caveat. Nothing is fabricated.
4. **Audit in-transaction.** Audit rows are written in the same DB transaction as
   the change, so no orphan audit rows and no unaudited changes.
5. **One origin.** The Next.js server proxies `/api`, `/ws`, `/health` to the
   backend — no CORS setup, no second host for tokens, WS upgrade works.
6. **Deterministic layouts.** Timeline lanes and graph layers are computed
   deterministically so the same case always renders identically (important for
   evidence presentation and screenshots).
7. **404 over 403 for cross-tenant cases** so ids are not confirmable.

Full rationale: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## 5. Run locally

```bash
./scripts/run_local.sh          # installs deps, migrates, builds, starts both
```

Prerequisites: **Python 3.11+ and Node 20+ only.** SQLite is the default database —
no Postgres, Redis, Neo4j or API keys required.

| URL | What |
|---|---|
| http://localhost:3000 | ForgeX UI |
| http://localhost:8000/docs | Interactive API docs |
| http://localhost:8000/health | Health probe |

Demo logins (seeded on first boot): `admin` / `lead` / `investigator` / `auditor`
with `ForgeX-<Role>-2026!` (accounts are `@forgex.local`).

Manual start and container deployment: see [`README.md`](README.md) §2–§3.

## 6. Environment variables

`backend/.env.example` documents every setting with its default. Highlights:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | random (dev) | **Required in production**, ≥32 chars |
| `ENVIRONMENT` | `development` | `production` enables strict validation |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/forgex.db` | Postgres via `postgresql+asyncpg://…` |
| `AUTO_CREATE_SCHEMA` | `true` | dev convenience; Alembic remains canonical |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | `60` / `7` | token lifetimes |
| `CORS_ORIGINS` | `localhost:3000` | only if the browser calls :8000 directly |
| `TRUSTED_PROXY` | `false` | set behind nginx to honor `X-Forwarded-For` |
| `COLLECTOR_TIMEOUT_SEC` / `SCRIPT_TIMEOUT_SEC` | `30` / `30` | sandbox caps |
| `MAX_CONCURRENT_JOBS` | `3` | job concurrency |
| `TASK_BACKEND` | `inline` | `celery` (needs `requirements-extra.txt`) |
| `GRAPH_STORE` | `sql` | `neo4j` optional |
| `LLM_PROVIDER` | `auto` | `anthropic` → `openai` → deterministic heuristic |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | optional |
| `EMBEDDING_PROVIDER` / `EMBEDDING_DIM` | `local` / `256` | offline deterministic by default |
| `BLOCKCHAIN_ANCHOR` | `local` | `sepolia` needs RPC URL + key |
| `RATE_LIMIT_API_PER_MIN` / `_FQL_PER_HOUR` / `_LOGIN_PER_MIN` | `100` / `20` / `10` | |
| `DEMO_SEED_ON_BOOT` | `false` | auto-seed the demo case at boot |

## 7. Database setup

* **Default (zero-setup):** SQLite at `backend/data/forgex.db`, created
  automatically on boot.
* **Production:**
  ```bash
  export DATABASE_URL=postgresql+asyncpg://forgex:***@db-host:5432/forgex
  cd backend && python -m alembic upgrade head
  ```
* **Schema:** 18 tables — `users`, `audit_logs`, `investigations`, `policies`,
  `ai_analyses`, `forensic_scripts`, `fql_queries`, `investigation_reports`, `jobs`,
  `collector_executions`, `script_executions`, `script_versions`,
  `evidence_items`, `findings`, `anchor_records`, `evidence_embeddings`,
  `graph_nodes`, `graph_edges` (migration `ce99d6c3fcd9`).
* **Seeding:** bootstrap users + default policy are created on first boot;
  `POST /api/v1/demo/seed` (ADMIN/LEAD) creates the deterministic demo case.
* **Container:** the backend image runs `alembic upgrade head` before uvicorn.

## 8. Test commands

```bash
# backend — 72 unit + integration tests
cd backend && python -m pytest

# lint
cd backend && ruff check .

# live end-to-end API smoke suite (server must be running)
python scripts/smoke_api.py

# frontend production build (type-checked)
cd frontend && npm run build
```

Coverage includes: FQL parse/validate/plan; policy allow/deny decisions;
sandbox escape attempts (import blocking, `__import__` bypass, file writes,
subprocess, CPU/timeout caps, garbage output); evidence hashing and integrity
verification; anchor chain verification; RBAC across all four roles; IDOR
isolation; report generation; AI promotion; audit writes; the error envelope;
pagination and filtering. Current status: **72/72 passing, ruff clean, smoke
suite ALL PASS, `npm run build` clean.**

## 9. Demo workflow

1. **Login** as `lead` → dashboard: ACTIVE CASES · EVIDENCE ITEMS · EXECUTIONS ·
   FINDINGS · HIGH-SEVERITY FINDINGS.
2. **Cases → New Case** (e.g. *“Ransomware precursor review”*).
3. **FQL console** — run
   `collect processes where name == 'powershell' and uptime_sec > 3600`;
   press **Validate** first to show AST + policy verdict, then **Execute**.
4. **Evidence** — SHA-256, collector, provenance, one-click integrity check.
5. **Script Lab** — choose *Windows Event Analysis* (or any of the 10), review the
   fully documented template, **Run** → artifacts and findings appear.
6. **Findings** — filter by severity/status; verify or dismiss (audited).
7. **Timeline** — SVG lane chart, hover for detail, click to sync the event log.
8. **Graph** — correlation graph with node inspector.
9. **AI** — **Correlate** → evidence-first "What happened?" with attack stages,
   indicators, MITRE techniques, confidence and caveats; ask a question in Q&A
   (answers cite evidence ids); promote an indicator to a finding.
10. **Reports** — generate FULL, poll to READY, download the PDF.
11. **Audit** — every action above with actor/target/metadata; CSV export.
12. **Settings** — RBAC matrix, user administration, policy authoring/validation,
    demo re-seed.

## 10. Limitations

1. Live Windows `.evtx` parsing and memory acquisition need host tooling outside
   the sandbox; templates consume the evidence the case holds.
2. Report export is PDF (reportlab); DOCX/XLSX are not implemented (CSV/JSON
   export exists for evidence and audit).
3. Neo4j, Celery/Redis, web3/Sepolia and LLM providers are optional integrations
   requiring `requirements-extra.txt` and their services.
4. Rate limiting is per-process; multi-replica deployments need a shared limiter.
5. Local embeddings are deterministic and offline — adequate for demo-scale
   retrieval, not production semantic search.
6. The WebSocket authenticates via a short-lived JWT in the query string
   (browsers cannot set WS headers); the socket is authorized per investigation.

## 11. Security

* **Authentication:** bcrypt password hashing, HS256 JWTs, short access token +
  rotating refresh cookie, login rate limiting (10/min/IP), role claims checked
  server-side on every request.
* **Authorization:** four roles (ADMIN, LEAD, INVESTIGATOR, AUDITOR) enforced at
  the API layer; UI nav mirrors but never replaces it. Cross-tenant case access
  returns 404. `/admin/audit` is ADMIN+AUDITOR only.
* **Sandbox:** separate process, meta-path import blocker + replaced `__import__`,
  filtered builtins, no filesystem/subprocess access, RLIMIT_CPU/RLIMIT_AS,
  wall-clock timeout, untrusted-output handling. Every attempt is tested.
* **Evidence integrity:** SHA-256 before persistence, on-demand re-verification,
  append-only anchor chain (local default, Sepolia optional).
* **Auditability:** in-transaction audit records for every state-changing action,
  immutable log with CSV export.
* **Input safety:** Pydantic validation on every request, parameterized ORM
  queries, standard error envelope that never leaks internals in production.
* **Transport:** single-origin deployment, security headers, nginx config with
  proper WebSocket upgrade and TLS-ready layout.
* **AI safety:** AI output is always separated from raw evidence, always cites
  real evidence ids, and always carries a caveat requiring analyst verification.

## 12. PPT → implementation mapping

| Slide / product concept | Implementation |
|---|---|
| Motto *"Write what you investigate — not how."* | FQL states intent; collectors decide how |
| Pipeline `INTENT → EXECUTION → EVIDENCE → CORRELATION → ANSWER` | `fql/` + `execution/` → `services/evidence` → `services/graph` → `ai/` |
| *"New programming language"* | FQL: Lark grammar, parser, AST, planner, validator (`backend/app/fql/`) |
| *"Scripts/functions"* | `forgex` SDK + 10 templates + Monaco Script Lab with versioning |
| *"Without triggering security solutions"* | Sandbox with import blocking, no `subprocess`/`os.system`, policy-gated collection, rate limits |
| Controlled execution pipeline | Validation → policy → sandbox → execute → artifacts → findings → evidence → audit → report |
| Dashboard (5 metrics) | `app/(main)/page.tsx` + `GET /stats/overview` |
| Cases | list/create/detail with 8 sub-pages |
| Evidence | list/filters/integrity verify/export |
| Script Lab + Template Library | template-first editor, 10 templates, global library page |
| Execution | jobs, executions list/detail, live WS status |
| Results / Findings | severity/status filters, verify/dismiss, promote-from-AI |
| Timeline | custom SVG lane chart |
| Correlation | graph page + `GraphStore` (SQL/Neo4j) |
| Reports | PDF generation + polling + download |
| Audit Logs | filters, metadata expansion, CSV export, ADMIN/AUDITOR gate |
| Settings | profile, RBAC matrix, users, policies (YAML), demo seed |
| Blockchain anchoring | `AnchorLedger`: local hash chain + Sepolia option |
| Standards NIST SP 800-86 / 800-61r3 / MITRE ATT&CK | forensic process, IR workflow, ATT&CK technique mapping in findings & AI output |
| Deterministic demo mode | `datasets/` + `POST /demo/seed`, all output labeled SYNTHETIC |
| Error states (10) | all implemented and surfaced with actionable messages |

---

**Status:** backend 72/72 tests passing, ruff clean, live API smoke suite all
pass; frontend production build clean, all 15 routes serving; deployment
artifacts (Docker, compose, nginx, `run_local.sh`) and documentation complete.
