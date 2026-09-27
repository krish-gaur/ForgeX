# ⬡ FORGE·X — Forensic Intelligence Workbench

**Team AIGloryThm · SIH 2026 · SIH26148 (NTRO, Blockchain & Cybersecurity)**

> *"Creation of scripts/functions with new programming language to commence Computer & Network forensic analysis without triggering security solutions."*

**Write what you investigate — not how.**

ForgeX is a two-layer forensic analysis workbench:

1. **FQL** (Forge Query Language) — a small purpose-built DSL that states *intent*
   (`collect processes where name == 'powershell'`) and compiles to audited,
   policy-gated, sandboxed collector runs.
2. **The ForgeX SDK** (`forgex` package) — Python-level forensic functions run inside a
   restricted child process with an import-blocking meta-path hook, resource caps,
   and no filesystem/network escape.

Both layers funnel through one controlled execution pipeline:

```
INTENT ─▶ VALIDATE ─▶ POLICY ─▶ SANDBOX ─▶ EXECUTE ─▶ ARTIFACTS ─▶ FINDINGS ─▶ EVIDENCE ─▶ AUDIT ─▶ REPORT
             (FQL)     (YAML)   (subprocess) (collector)  (hash/SHA-256)  (correlate)  (chain)  (PDF)
```

Every finding the AI produces cites real `evidence_id`s collected in the same case —
AI never invents forensic evidence. Evidence is hashed with SHA-256 before it touches
the database and anchored to an append-only hash chain (Sepolia testnet optional).

---

## 1. Repository layout

```
ForgeX/
├── backend/                  # FastAPI application + FQL engine + SDK runtime
│   ├── app/
│   │   ├── api/v1/           # REST routers (auth, investigations, evidence, fql,
│   │   │                     #   scripts, findings, ai, reports, admin, demo)
│   │   ├── core/             # security (JWT/bcrypt), RBAC, errors, audit chain,
│   │   │                     #   websocket hub, logging, pagination
│   │   ├── db/               # SQLAlchemy models + session + alembic env
│   │   ├── fql/              # Lark grammar → parser → collectors → planner
│   │   ├── collectors/       # processes / files / network / users / events / timeline
│   │   ├── execution/        # sandbox: child-process runner, import blocker, caps
│   │   ├── policy/           # YAML policy loader + enforcement gate
│   │   ├── services/         # pipeline (job runners), evidence, graph, reports, anchor
│   │   ├── ai/               # correlation engine (LLM or deterministic heuristic),
│   │   │                     #   RAG (local embeddings), Q&A, finding promotion
│   │   ├── graph/            # GraphStore interface (SQL default, Neo4j optional)
│   │   ├── jobs/             # executor (inline asyncio default, Celery optional)
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── config.py         # pydantic-settings (see backend/.env.example)
│   │   └── main.py           # app factory, middleware, router mount, WS endpoint
│   ├── forgex_sdk/           # the `forgex` Python SDK shipped to sandboxes
│   ├── templates/functions/  # 10 forensic function templates (frontmatter + code)
│   ├── alembic/              # migrations (rev 3a8f2273dffa, 19 tables)
│   ├── tests/                # 72 unit/integration tests (pytest)
│   ├── requirements.txt      # core pinned deps (runs on SQLite, zero services)
│   ├── requirements-extra.txt# optional: postgres/neo4j/celery/web3/anthropic/openai
│   └── pytest.ini, ruff.toml
├── frontend/                 # Next.js 15 (App Router, React 19) security-lab UI
│   ├── app/                  # dashboard, cases, evidence, lab, executions, findings,
│   │                         #   timeline, graph, ai, reports, templates, audit, settings
│   ├── components/           # Shell (nav + RBAC), Monaco, FQL console, UI kit
│   ├── lib/                  # typed API client, auth, WS, data hooks, formatters
│   └── next.config.mjs       # dev proxy: /api, /ws, /health → :8000
├── datasets/                 # synthetic forensic sample data (SYNTHETIC provenance)
├── docs/                     # ARCHITECTURE.md, ASSUMPTIONS.md
├── infrastructure/
│   ├── docker/               # Dockerfile.backend, Dockerfile.frontend, docker-compose.yml
│   └── nginx/                # edge reverse proxy config
├── scripts/
│   ├── run_local.sh          # one-command local run (backend + frontend)
│   └── smoke_api.py          # end-to-end API smoke suite
└── REPORT.md                 # 12-part implementation report (§28)
```

---

## 2. Run locally (no Docker, ~2 minutes)

**Prerequisites:** Python 3.11+, Node 20+, nothing else. SQLite is the default
database — no Postgres, Redis, or Neo4j required.

```bash
# one command: installs deps, migrates, builds frontend, starts both services
./scripts/run_local.sh
```

Then open **http://localhost:3000** and sign in with a seeded demo account:

| Username | Password | Role |
|---|---|---|
| `admin` | `ForgeX-Admin-2026!` | Full access, user + policy administration |
| `lead` | `ForgeX-Lead-2026!` | Case owner: create cases, run collectors, seed demo |
| `investigator` | `ForgeX-Investigator-2026!` | Run collectors/scripts, own findings |
| `auditor` | `ForgeX-Auditor-2026!` | Read-only + audit log access |

(Accounts end in `@forgex.local` and are created by the bootstrap seeder on first boot.
Change all four immediately in any non-demo deployment.)

### Manual start (what the script does)

```bash
# backend
cd backend
python3 -m pip install -r requirements.txt
cp .env.example .env                  # optional; defaults are runnable
python3 -m alembic upgrade head
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                           # or: npm run build && npm start
```

* API interactive docs: **http://localhost:8000/docs**
* Health probe: **http://localhost:8000/health**
* The Next.js dev server proxies `/api/*`, `/ws`, `/health` to `:8000`, so the
  browser only ever talks to `:3000` — no CORS configuration needed.

---

## 3. Run with Docker (production shape)

```bash
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export SECRET_KEY

# postgres + backend + frontend
docker compose -f infrastructure/docker/docker-compose.yml up --build

# optional: celery worker, neo4j graph store, nginx edge
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile celery --profile neo4j --profile edge up --build
```

The backend container runs `alembic upgrade head` before uvicorn starts.
`frontend` talks to `backend` through the compose network (`BACKEND_ORIGIN`).

---

## 4. Environment variables

Copy `backend/.env.example` → `backend/.env`. Every variable has a working
default, so the file is optional for local runs. The security-relevant ones:

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | *(random, ephemeral)* | **Must** be set in production (≥32 chars) |
| `ENVIRONMENT` | `development` | `production` enforces strict settings + error hiding |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/forgex.db` | Use `postgresql+asyncpg://…` in production |
| `AUTO_CREATE_SCHEMA` | `true` | Alembic stays canonical; run `alembic upgrade head` |
| `ACCESS_TOKEN_TTL_MINUTES` / `REFRESH_TOKEN_TTL_DAYS` | `60` / `7` | |
| `CORS_ORIGINS` | `http://localhost:3000,…` | Only needed if the browser calls :8000 directly |
| `COLLECTOR_TIMEOUT_SEC` / `SCRIPT_TIMEOUT_SEC` | `30` | Hard resource caps enforced by the sandbox |
| `TASK_BACKEND` | `inline` | `celery` requires `requirements-extra.txt` + Redis |
| `GRAPH_STORE` | `sql` | `neo4j` optional |
| `LLM_PROVIDER` | `auto` | `anthropic` → `openai` → deterministic heuristic fallback |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | *(empty)* | Without keys, AI uses the built-in evidence-citing rule engine |
| `BLOCKCHAIN_ANCHOR` | `local` | `sepolia` needs `SEPOLIA_RPC_URL` + `SEPOLIA_PRIVATE_KEY` |
| `RATE_LIMIT_API_PER_MIN` / `_FQL_PER_HOUR` / `_LOGIN_PER_MIN` | `100` / `20` / `10` | |

Full annotated list: **`backend/.env.example`**.

---

## 5. Database setup

* **Local dev / demo:** SQLite (`backend/data/forgex.db`) created automatically.
* **Production:** `DATABASE_URL=postgresql+asyncpg://forgex:***@host/forgex`
  then `python -m alembic upgrade head` (schema: 19 tables — users, investigations,
  evidence, artifacts, scripts, versions, jobs, executions, findings, analyses,
  reports, audit_logs, policies, anchor entries, graph nodes/edges, …).
* Bootstrap users + the default policy are seeded on first boot.
* `POST /api/v1/demo/seed` (ADMIN/LEAD) creates the deterministic
  **DEMO-Corp-Breach-2026** case with clearly-labeled **SYNTHETIC** data.

---

## 6. Tests

```bash
cd backend
python -m pytest                 # 72 unit + integration tests
ruff check .                     # lint (ruff.toml project config)
python ../scripts/smoke_api.py   # live end-to-end smoke suite against a running server
```

The suite covers the FQL parser/planner, policy gate decisions, sandbox escape
attempts (import blocking, subprocess blocking, filesystem denial, CPU/timeout caps),
evidence hashing + integrity verification, the hash-chain anchor, RBAC matrix,
IDOR isolation (investigators get 404 on others' cases), report generation, AI
promotion, audit writes, and the error envelope.

```bash
cd frontend
npm run build                    # production build (type-checked)
```

---

## 7. Demo workflow (the journey to show)

1. **Sign in** as `lead` → dashboard shows ACTIVE CASES / EVIDENCE ITEMS /
   EXECUTIONS / FINDINGS / HIGH-SEVERITY FINDINGS counters.
2. **Cases → New case** (e.g. *“Ransomware precursor review”*).
3. **FQL console** on the case overview:
   `collect processes where name == 'powershell' and uptime_sec > 3600`
   → *Validate* shows the parsed AST, estimated collectors, and the policy verdict
   before anything runs → *Execute*.
4. **Evidence** — each item shows SHA-256, source collector, provenance, and a
   one-click integrity re-verification.
5. **Script Lab** — pick a template (10 available: Windows Event, Registry, File
   Metadata, Network Artifact, Process, Memory, Browser Artifact, Timeline
   Generation, Hash Verification, Custom). You never start from an empty editor;
   every template ships with imports, function structure, parameters, expected
   output, error handling, forensic context, and inline docs. Run it → artifacts
   and findings appear.
6. **Findings** — filter by severity/status, promote AI indicators to findings,
   verify or dismiss with an audit trail.
7. **Timeline** — custom SVG lane chart of every event, severity/type colored.
8. **Graph** — users → processes → files/network → events correlation graph.
9. **AI** — *Correlate* produces the evidence-first "What happened?" analysis
   (attack stages, suspicious indicators, MITRE techniques, confidence, caveats).
   Q&A answers questions citing evidence IDs.
10. **Reports** — FULL / SUMMARY / CHAIN_OF_CUSTODY → poll → download PDF.
11. **Audit log** — every action above, with actor, target, metadata, CSV export.
12. **Settings** — users, RBAC matrix, policies (YAML authoring + validation),
    demo re-seed.

All demo content is generated from `datasets/` and is explicitly labeled
**SYNTHETIC**.

---

## 8. Architecture highlights

* **FQL compiler** — Lark grammar → AST → planner → collector plan; `validate`
  runs the full parse + policy preview *without* executing anything.
* **Sandbox** — forensic functions run as a plain `sys.executable` child with:
  a meta-path `ImportBlocker` (`__import__` is replaced, so `sys.modules` cache
  hits can't bypass it), `SAFE_BUILTINS` (incl. exception types), no file writes,
  no subprocess, RLIMIT_CPU/AS caps, and untrusted-output handling (empty or
  garbage stdout, SIGXCPU/SIGKILL return codes) that still produces a proper
  job status.
* **Evidence integrity** — SHA-256 computed before the row is written;
  `/evidence/{id}?verify=true` recomputes and compares.
* **Anchor chain** — local append-only SHA-256 chain by default; Sepolia
  anchoring when configured (web3 is lazily imported).
* **AI** — provider abstraction: Anthropic → OpenAI → deterministic rule engine
  that emits `evidence_id` citations and explicit caveats. RAG uses local
  deterministic embeddings (no network, no key) by default.
* **Async jobs** — inline asyncio executor by default; `TASK_BACKEND=celery`
  enqueues to a worker that runs the *same* `execute_job` code path. Live status
  streams over `ws://…/ws?token=JWT&investigation_id=ID`.

Detailed design decisions and trade-offs: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Assumptions and deliberate deviations from the reference document:
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

---

## 9. Standards & scope

Aligned with **NIST SP 800-86** (forensic process), **NIST SP 800-61r3** (incident
response) and **MITRE ATT&CK** technique mapping. ForgeX collects and correlates
artifacts from *authorized, in-scope* systems only; every action is audited.

Limitations and known boundaries: [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) §9
and [`REPORT.md`](REPORT.md) §10.
