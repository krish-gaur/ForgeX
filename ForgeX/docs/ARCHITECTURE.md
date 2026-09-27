# ForgeX Architecture

**Team AIGloryThm · SIH26148** — decision record for how the platform was built and why.

---

## 1. The problem, restated as an engineering requirement

SIH26148 asks for a *new programming language* to start computer & network forensic
analysis **without triggering security solutions**. That decomposes into four hard
requirements:

| Requirement | Engineering consequence |
|---|---|
| A new language for forensic intent | A real DSL (FQL) with its own grammar, parser, and semantics — not config files |
| Scripts/functions | A second, richer layer (Python-based SDK) executed under a sandbox |
| "Without triggering security solutions" | Execution must avoid noisy primitives: no live shelling out to `cmd`/`bash` from the target's perspective, no broad file scans, no obvious `subprocess`/`os.system` calls in user code, rate-limited and policy-gated collection |
| Forensic credibility | Evidence hashing, chain-of-custody, audit trail, provenance labeling, report export |

## 2. Two-layer language design

### 2.1 FQL — intent layer

```
collect <collector> [where <predicate>] [last <window>] [limit <n>]
```

* **Grammar:** Lark (Earley), `backend/app/fql/`.
* **Pipeline:** source → parse → AST → *validate* (AST + estimated collectors +
  policy preview) → plan → execute.
* **Why a separate intent layer:** the statement of *what* to collect is
  separately validatable and auditable. Validation never executes anything, so a
  bad query can be caught before touching a system.
* **Compilation target:** the six collectors (`processes`, `files`, `network`,
  `users`, `events`, `timeline`) — the same primitives the SDK uses, so there is
  exactly one execution engine.

### 2.2 ForgeX SDK — function layer

A small Python package (`backend/forgex_sdk/`, imported as `forgex`) providing
forensic primitives: `Evidence`, `Artifact`, `File`, `Process`, `Registry`,
`Event`, `Network`, `Memory`, `Timeline`, `Hash`, `Metadata`, `Finding`,
`ChainOfCustody`.

* Runs as a **separate OS process** (`sys.executable -m forgex._runtime`), never
  in-process — a crash or resource bomb cannot take the API down.
* **Import blocking:** a `MetaPathFinder` installed on `sys.meta_path` blocks all
  modules outside an explicit allowlist. Critically, `__import__` is *also*
  replaced, because leaving the builtin in place lets user code hit the
  `sys.modules` cache and bypass the finder entirely.
* **Builtin filtering:** `SAFE_BUILTINS` — no `open`, `exec`, `eval`, `compile`,
  `input`, `breakpoint`; exception types are deliberately *kept* so that
  well-written error handling in templates still works.
* **Resource caps:** `RLIMIT_CPU`/`RLIMIT_AS` + wall-clock timeout; SIGXCPU and
  SIGKILL return codes are treated as first-class outcomes, not crashes.
* **Untrusted output handling:** the child's stdout/artifact file is never
  trusted — empty, non-JSON, or truncated output yields a normal FAILED job with
  a message instead of a bogus success.

**Why not a custom VM/bytecode language for the function layer:** the problem asks
for a language to *commence* analysis; a hardened, capability-restricted Python
subset with a purpose-built SDK gives strictly more forensic expressiveness than a
bespoke VM, while the *intent* language (FQL) is genuinely new and purpose-built.
This satisfies both the functional intent and the letter of the requirement.

## 3. Controlled execution pipeline

```
User intent (FQL or script)
  → Validation      syntax/schema, template integrity
  → Policy gate     YAML policy: allowed/restricted collectors, field
                    restrictions, rate limits, required role, case status
  → Sandbox         child process, import blocker, caps
  → Execution       collector / function run
  → Artifact proc   normalize, dedupe, SHA-256, type detection
  → Findings        extractor → correlation → MITRE mapping
  → Evidence        persist, index for RAG, graph nodes/edges
  → Audit log       append-only, in the same transaction
  → Report          PDF (reportlab) behind a renderer interface
```

Key decisions:

* **Policy is enforced server-side, before collectors run**, and the same policy
  is what `/fql/validate` previews — what you see is what will be enforced.
* **Audit writes happen inside the same DB transaction** as the audited change,
  so a failed action never leaves an orphan audit row, and a successful one
  never lacks one.
* **Jobs are first-class rows** (`Job` table) so execution survives API restarts
  and is observable over WebSocket.

## 4. Sandbox hardening details

| Attack | Mitigation | Test |
|---|---|---|
| `import os` / `import socket` | meta-path `ImportBlocker` | `test_sandbox_*` |
| `__import__("os")` bypass via module cache | `__import__` replaced with `_safe_import` gate | covered |
| `open()` file writes | removed from builtins | covered |
| subprocess/spawn | removed from builtins + blocked imports | covered |
| CPU exhaustion | `RLIMIT_CPU` + wall-clock kill, negative return codes handled | covered |
| Memory exhaustion | `RLIMIT_AS` | covered |
| garbage stdout / empty artifact | treated as FAILED with message | covered |
| host filesystem discovery | collectors restricted by policy `excluded_paths`, `max_depth`, `max_file_bytes` | covered |

**Process launch note:** the child is started as plain `python -m forgex._runtime`
with an explicit environment. Using `python -I`/`-E` breaks the runtime's own
import of its package; environment sanitization is done in code instead.

## 5. Evidence, integrity, anchoring

* SHA-256 is computed **before** the DB row is written; the stored hash is the
  identity of the artifact.
* `GET /evidence/{id}?verify=true` recomputes and returns
  `{matches_stored, recomputed_hash}`.
* `AnchorLedger` interface:
  * **local (default):** append-only SHA-256 hash chain, each entry hashing the
    previous entry — verifiable via `/investigations/{id}/anchor-chain/verify`.
  * **sepolia (optional):** additionally anchors batch roots to the Sepolia
    testnet via `web3`, lazily imported so the dependency stays optional.

## 6. Correlation graph

`GraphStore` interface with two implementations:

* **SQL (default):** nodes + edges tables, deterministic layered layout computed
  in Python (users → processes → files/network → events). Works with zero extra
  infrastructure.
* **Neo4j (optional):** same interface, `neo4j` driver imported lazily.

Node ids never derive from possibly-missing payload fields — a missing field
falls back to an evidence-id suffix, so ids are always stable and unique.

## 7. AI subsystem (evidence-first, never fabricating)

Provider abstraction in `app/ai/`:

1. `LLM_PROVIDER=anthropic` → Claude
2. `openai` → GPT
3. `auto` → first available key, else
4. **deterministic heuristic engine** (always available, offline)

The deterministic engine emits the *same* structured output shape:
`what_happened`, `attack_stages`, `suspicious_indicators` (each with
`evidence_ids`), `mitre_techniques`, `gaps`, `confidence`, and an explicit
`caveat` that the output is machine-generated and requires analyst verification.

**Hard rule enforced in code:** every indicator/finding carries the
`evidence_id`s it was derived from. Promotion to a finding copies those ids.
Nothing is ever synthesized without collected evidence behind it.

RAG uses local deterministic hashing embeddings (256-dim, no network, no key) by
default; `EMBEDDING_PROVIDER=openai` upgrades to real embeddings when a key is
present. This keeps the demo fully functional offline while preserving the
architecture for production embeddings.

## 8. Async jobs

Inline asyncio executor by default; `TASK_BACKEND=celery` enqueues to a worker
that runs the *same* `execute_job` code path. Live status streams over
`ws://…/ws?token=JWT&investigation_id=ID`.

### 8.1 Job submission and the commit-visibility race

`executor.submit()` flushes the `Job` row inside the **request** transaction,
which commits a few statements later (the in-transaction audit row + `commit`).
The inline task is created at `submit()` time, so it can start — and open its own
DB connection — **before** the row is committed. On SQLite an uncommitted row is
invisible to other connections, so the task used to find nothing and silently
drop the job, leaving it `QUEUED` forever. This surfaced as an intermittent
"collection job never completes" under load.

Three defenses, all tested (`tests/test_jobs.py`):

1. **Visibility wait** — `execute_job` polls (fresh session per attempt) for up to
   `JOB_VISIBILITY_TIMEOUT_SEC` (20s) for the row to appear, instead of dropping it.
   The same wait protects Celery workers, which can pick a task up before the API
   transaction commits.
2. **No silent drops** — a job that never becomes visible is logged at `error`
   level (`job_row_not_visible`).
3. **Startup recovery** — on boot, the inline executor re-enqueues any jobs left
   `QUEUED` by a previous process (crash/restart safety net), logged as
   `orphaned_jobs_requeued`.

## 9. Frontend architecture

* Next.js 15 App Router, React 19, TypeScript, Tailwind, Monaco, `@xyflow/react`.
* **All browser traffic goes to `:3000`**; `next.config.mjs` rewrites `/api/*`,
  `/ws`, `/health` to the backend. One origin → no CORS, no token leakage to a
  second host, and the WebSocket upgrade works through the dev server.
* Typed API client (`lib/api.ts`) with the error envelope unwrapped centrally.
* RBAC in the UI mirrors the server: nav items and pages carry `roles` and the
  server independently rejects (e.g. `/admin/audit` is ADMIN + AUDITOR only).
* Template-first Script Lab: the template library is the entry point; the empty
  editor is not a reachable state.
* Timeline is a hand-rolled SVG lane chart (no chart library needed, fully
  controllable, deterministic layout); the correlation graph uses `@xyflow/react`
  with a custom node type and a deterministic layered layout.

## 10. Deployment

* **Local:** `scripts/run_local.sh` (SQLite, no external services).
* **Container:** `infrastructure/docker/` — backend image runs Alembic then
  uvicorn; frontend image is a standalone Next build; `nginx/forgex.conf` adds
  TLS-ready proxying with a proper WebSocket upgrade block.
* Optional profiles: `celery` (Redis + worker), `neo4j`, `edge`.

## 11. Deliberate deviations from the reference document

See [`ASSUMPTIONS.md`](ASSUMPTIONS.md) for the full list with rationale. In short:
SQLite as the runnable default (Postgres supported via `DATABASE_URL`), the
local hash chain as the default anchor (Sepolia optional), the deterministic
heuristic engine as the default AI (LLM optional), and inline asyncio jobs as the
default executor (Celery optional). In each case the optional production
component is behind an interface and actually implemented — not stubbed.
