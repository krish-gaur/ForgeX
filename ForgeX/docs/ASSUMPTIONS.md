# ForgeX — Assumptions & Decisions Log

Every engineering decision that required a judgment call, and the reasoning.
Where a decision deviates from the reference architecture document, the reason
is stated. Reference files were the primary source of truth; where they
conflicted with functional intent or runnability, functional intent won.

---

## 1. Deployment shape

**Decision:** SQLite (aiosqlite) is the default, zero-setup database;
PostgreSQL is fully supported via `DATABASE_URL=postgresql+asyncpg://…`.

**Why:** the judging/demo environment has no guaranteed Postgres. A platform
that cannot run cannot be evaluated. The ORM, migrations, and all queries are
written to be portable; only the driver line changes.

**Assumption recorded:** a real deployment sets `DATABASE_URL` and runs
`alembic upgrade head`. `AUTO_CREATE_SCHEMA=true` exists as a dev convenience
only and is documented as such.

## 2. Evidence anchoring

**Decision:** an append-only local SHA-256 hash chain is the default anchor;
Sepolia testnet anchoring is implemented behind the same interface and enabled
with `BLOCKCHAIN_ANCHOR=sepolia`.

**Why:** the problem statement is in the Blockchain & Cybersecurity theme, so
the anchor is a first-class feature — but requiring a funded wallet and testnet
connectivity to boot the demo would break the runnability requirement. Both
paths are real implementations; neither is a stub.

**Assumption recorded:** `Sepolia` was chosen over mainnet deliberately (no
real funds, no irreversible writes during evaluation).

## 3. AI provider strategy

**Decision:** provider abstraction with a deterministic, offline, evidence-citing
heuristic engine as the guaranteed baseline. Anthropic → OpenAI → heuristic.

**Why:** "no fake AI responses" is an explicit acceptance criterion. A heuristic
engine that derives its output *from real collected evidence* and states its own
caveats is genuinely functional and never fabricates. LLM keys upgrade the same
output shape without changing the pipeline.

**Assumption recorded:** no API keys are present in the evaluation environment;
therefore the default path must be complete on its own.

## 4. Embeddings / RAG

**Decision:** local deterministic hashing embeddings (256-dim) by default;
`EMBEDDING_PROVIDER=openai` upgrades to real embeddings.

**Why:** retrieval must work offline and deterministically for the demo, while
the architecture stays swappable.

## 5. Task execution

**Decision:** inline asyncio executor by default; Celery behind
`TASK_BACKEND=celery` running the identical `execute_job` code path.

**Why:** Celery + Redis is another service that may not exist in the eval
environment. Sharing one execution function means behavior cannot drift between
modes — the Celery worker imports and runs the same function the inline executor
does. (This required refactoring the executor so job dispatch, status
transitions, and WebSocket fan-out live in `execute_job()` rather than inside
the inline executor's `_run`.)

## 6. Language layers

**Decision:** two layers — FQL (new, purpose-built DSL) for intent, and a
hardened Python subset + `forgex` SDK for functions.

**Why:** a bespoke bytecode VM for the function layer would be less capable and
substantially riskier (more untested code in the security boundary). FQL is
genuinely new and is the "new programming language" the problem asks for; the
SDK layer is where forensic depth lives. Sandbox hardening is documented in
`docs/ARCHITECTURE.md` §4.

## 7. Sandbox specifics

* Child is launched as `python -m forgex._runtime` with an explicit env — **not**
  `python -I/-E`, which breaks the runtime importing its own package.
* `__import__` is replaced because a builtin `__import__` reaches the
  `sys.modules` cache and bypasses a `meta_path` import blocker.
* `SAFE_BUILTINS` retains exception types (so template error handling works) but
  drops `open`, `eval`, `exec`, `compile`, `input`, `breakpoint`.
* Child output is treated as untrusted: empty/garbage output, SIGXCPU and SIGKILL
  all produce a normal FAILED job with a message.

## 8. Data & domain assumptions

* **Bootstrap accounts** (`admin`, `lead`, `investigator`, `auditor`, all
  `@forgex.local`, password `ForgeX-<Role>-2026!`) exist so the demo can start
  from a known state. Documented in the README; meant to be rotated.
* **RBAC semantics:**
  * ADMIN — everything, plus user & policy administration.
  * LEAD — case owner: create/assign cases, run collectors, seed the demo,
    read policies. **Cannot** read the audit log (server-enforced 403).
  * INVESTIGATOR — run collectors/scripts on assigned cases, manage own
    findings.
  * AUDITOR — read-only across cases + audit log access.
* **IDOR handling:** investigators receive **404** (not 403) for other users'
  cases, to avoid confirming the existence of a case id.
* **Demo dataset** lives in `datasets/` and is labeled **SYNTHETIC** in
  provenance fields, the UI, and reports.
* **Timestamps** are normalized to UTC everywhere; SQLite returns naive
  datetimes, so a normalization helper is applied at the boundaries.

## 9. Known limitations

1. **Collectors are dataset-backed for demo cases** and live-host backed for
   `processes`/`network`/`users` via psutil. Live Windows `.evtx` parsing and
   memory acquisition require platform tooling that is out of scope for the
   sandbox; the SDK templates consume whatever evidence the case holds.
2. **Report rendering is reportlab-based PDF** (DOCX/XLSX export is not
   implemented; CSV/JSON export exists for evidence and the audit log).
3. **Neo4j, Celery, web3, LLM providers** are optional integrations requiring
   `requirements-extra.txt` and their services; the platform degrades to working
   defaults without them.
4. **Rate limiting is in-process** (per-worker). A multi-replica deployment needs
   a shared limiter (Redis) — noted, not implemented.
5. **The WebSocket channel is unauthenticated by design only via JWT in the query
   string** (browsers cannot set WS headers). The token is short-lived and the
   socket is authorized per investigation.
6. **Local embeddings are not semantically strong** — they are deterministic and
   offline, adequate for evidence retrieval in the demo, not for production-scale
   semantic search.

## 10. Frontend/UX assumptions

* One origin (`:3000`) proxies `/api`, `/ws`, `/health` to the backend — no CORS
  configuration is required for the standard setup.
* The Script Lab is **template-first**: the empty editor is not a reachable
  state. "Custom" is itself a template.
* Dark "security-lab" aesthetic was an explicit product requirement; the design
  system is built in `app/globals.css` + `components/ui.tsx` rather than a
  component library, to avoid generic SaaS styling.
