#!/usr/bin/env bash
# ForgeX — one-command local run (no Docker).
#   backend : FastAPI on :8000 (SQLite by default)
#   frontend: Next.js  on :3000 (proxies /api, /ws, /health → :8000)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

echo "▸ ForgeX local launcher"

# ---- backend -----------------------------------------------------------------
cd "$ROOT/backend"
if ! $PYTHON -c "import fastapi, uvicorn, sqlalchemy" 2>/dev/null; then
  echo "▸ installing backend dependencies…"
  $PYTHON -m pip install -r requirements.txt
fi
if [ ! -f .env ]; then
  echo "▸ no backend/.env found — copying .env.example (defaults are runnable as-is)"
  cp .env.example .env
fi
echo "▸ applying database migrations (alembic upgrade head)…"
$PYTHON -m alembic upgrade head >/dev/null 2>&1 || echo "  (alembic skipped — AUTO_CREATE_SCHEMA will create tables on boot)"

echo "▸ starting FastAPI on http://localhost:8000 …"
$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACK_PID=$!

# ---- frontend ----------------------------------------------------------------
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "▸ installing frontend dependencies (npm ci)…"
  if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
fi
echo "▸ building Next.js frontend…"
npm run build >/dev/null

echo "▸ starting Next.js on http://localhost:3000 …"
npm run start &
FRONT_PID=$!

cleanup() {
  echo; echo "▸ shutting down…"
  kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
  wait "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cat <<'BANNER'

  ╔═══════════════════════════════════════════════════════════════╗
  ║  FORGE·X  — Forensic Intelligence Workbench                   ║
  ║  UI      : http://localhost:3000                              ║
  ║  API docs: http://localhost:8000/docs                         ║
  ║                                                               ║
  ║  Demo logins (seeded on first boot):                          ║
  ║    admin        / ForgeX-Admin-2026!                          ║
  ║    lead         / ForgeX-Lead-2026!                           ║
  ║    investigator / ForgeX-Investigator-2026!                   ║
  ║    auditor      / ForgeX-Auditor-2026!                        ║
  ╚═══════════════════════════════════════════════════════════════╝

BANNER

wait
