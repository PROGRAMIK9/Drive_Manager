#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for the React frontend." >&2
  exit 1
fi
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "Missing backend/.env. Copy backend/.env.example to backend/.env and fill in the existing database/auth settings." >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm ci)
fi

if [[ -x "$BACKEND_DIR/.venv/bin/uvicorn" && -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  BACKEND_RUN=("$BACKEND_DIR/.venv/bin/uvicorn" app.main:app)
  PYTHON_RUN=("$BACKEND_DIR/.venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
  BACKEND_RUN=(uv run --frozen uvicorn app.main:app)
  PYTHON_RUN=(uv run --frozen python)
else
  echo "Backend dependencies are missing. Create backend/.venv or install uv and run uv sync in backend/." >&2
  exit 1
fi

if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
  echo "Initializing or migrating the database..."
  (cd "$BACKEND_DIR" && PYTHONPATH=. "${PYTHON_RUN[@]}" scripts/bootstrap_db.py)
fi

backend_pid=""
frontend_pid=""
cleanup() {
  trap - EXIT INT TERM
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND_DIR"
  export PYTHONPATH=.
  exec "${BACKEND_RUN[@]}" --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-8000}"
) &
backend_pid=$!
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host "${FRONTEND_HOST:-127.0.0.1}" --port "${FRONTEND_PORT:-5173}"
) &
frontend_pid=$!

printf 'Backend:  http://%s:%s\n' "${BACKEND_HOST:-127.0.0.1}" "${BACKEND_PORT:-8000}"
printf 'Frontend: http://%s:%s\n' "${FRONTEND_HOST:-127.0.0.1}" "${FRONTEND_PORT:-5173}"
printf 'Press Ctrl+C to stop both services.\n'

# Monitor both children and report which service stopped.
set +e
wait -n "$backend_pid" "$frontend_pid"
status=$?
set -e
if ! kill -0 "$backend_pid" 2>/dev/null; then
  echo "Backend exited with status $status; stopping frontend." >&2
else
  echo "Frontend exited with status $status; stopping backend." >&2
fi
exit "$status"
