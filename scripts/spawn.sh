#!/usr/bin/env bash
# Verda — spawn a service detached from the parent (make) so make can
# return without taking the child with it. Used by `make stack` only.
#
# Usage:
#   scripts/spawn.sh backend
#   scripts/spawn.sh frontend
set -euo pipefail

ROLE="${1:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

case "$ROLE" in
  backend)
    LOG=/tmp/wakili-backend.log
    PIDFILE=/tmp/wakili-backend.pid
    CMD=(bash -c "cd backend && PYTHONPATH=. ../.venv/bin/python -m uvicorn wakili.main:app --host 127.0.0.1 --port 8765 --log-level info")
    ;;
  frontend)
    LOG=/tmp/wakili-frontend.log
    PIDFILE=/tmp/wakili-frontend.pid
    CMD=(bash -c "cd frontend && npm run start -- --port 3000")
    ;;
  *)
    echo "usage: $0 {backend|frontend}" >&2
    exit 2
    ;;
esac

# setsid + nohup + redirected fds + < /dev/null + disown — belt-and-braces
# detachment so the child does not die with make.
nohup setsid "${CMD[@]}" >"$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
disown 2>/dev/null || true
echo "$ROLE spawned (pid $(cat "$PIDFILE")), logs: $LOG"
