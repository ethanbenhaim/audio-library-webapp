#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin/activate"

# ── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[start]${NC} $*"; }
ok()   { echo -e "${GREEN}[start]${NC} $*"; }
warn() { echo -e "${YELLOW}[start]${NC} $*"; }
die()  { echo -e "${RED}[start]${NC} $*" >&2; exit 1; }

PIDS=()

cleanup() {
  echo ""
  log "Shutting down…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  ok "All services stopped."
}
trap cleanup EXIT INT TERM

# ── Preflight checks ────────────────────────────────────────────────────────
[[ -f "$VENV" ]] || die "Python venv not found. Run: python3.11 -m venv .venv && source .venv/bin/activate && pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt"

[[ -d "$ROOT/frontend/node_modules" ]] || die "Frontend deps missing. Run: cd frontend && npm install"

# ── Kill any stale processes from a previous run ────────────────────────────
for port in 8000 5173; do
  pid=$(lsof -ti ":$port" 2>/dev/null) && kill $pid 2>/dev/null && warn "Killed stale process on :$port" || true
done

# ── Redis ───────────────────────────────────────────────────────────────────
if redis-cli ping &>/dev/null; then
  ok "Redis already running"
else
  log "Starting Redis…"
  brew services start redis
  sleep 1
  redis-cli ping &>/dev/null || die "Redis failed to start"
  ok "Redis started"
fi

# ── FastAPI backend ─────────────────────────────────────────────────────────
log "Starting FastAPI backend on :8000…"
(
  source "$VENV"
  cd "$ROOT/backend"
  uvicorn app.main:app --reload --port 8000
) &
PIDS+=($!)

# ── Celery worker ───────────────────────────────────────────────────────────
log "Starting Celery worker…"
(
  source "$VENV"
  cd "$ROOT/backend"
  celery -A app.celery_app:celery_app worker --loglevel=info --concurrency=1
) &
PIDS+=($!)

# ── Frontend dev server ─────────────────────────────────────────────────────
log "Starting Vite frontend on :5173…"
(
  cd "$ROOT/frontend"
  npm run dev
) &
PIDS+=($!)

ok "All services running. Open http://localhost:5173"
log "Press Ctrl+C to stop everything."

wait
