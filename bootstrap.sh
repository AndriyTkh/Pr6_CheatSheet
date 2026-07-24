#!/usr/bin/env bash
# One-shot dev bootstrap for CheatSheet (backend + frontend). POSIX companion
# to bootstrap.ps1 — see that file's header for the full contract. Idempotent.
#
#   ./bootstrap.sh                 # full setup, default port
#   ./bootstrap.sh --db-port 55432 # native Postgres owns 5432; publish elsewhere
#   ./bootstrap.sh --backend       # backend only   (--frontend for the other)
#   ./bootstrap.sh --skip-db       # no Docker/migrations; DB tests will skip
#   ./bootstrap.sh --test          # run pytest + npm build after setup
#
# Logs a full transcript to logs/bootstrap-<timestamp>.log by default
# (git-ignored). --no-log disables it; --log-file PATH overrides the path.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

do_backend=0; do_frontend=0; skip_db=0; run_test=0; db_port=5432; no_log=0; log_file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --backend)  do_backend=1 ;;
    --frontend) do_frontend=1 ;;
    --skip-db)  skip_db=1 ;;
    --test)     run_test=1 ;;
    --db-port)  db_port="$2"; shift ;;
    --log-file) log_file="$2"; shift ;;
    --no-log)   no_log=1 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done
# No target flag means "do both".
if [ "$do_backend" -eq 0 ] && [ "$do_frontend" -eq 0 ]; then do_backend=1; do_frontend=1; fi

# Log by default. Re-exec once with everything piped through tee so both stdout
# and stderr land in the file and on screen. The guard env var stops recursion.
if [ "$no_log" -eq 0 ] && [ -z "${_BOOTSTRAP_LOGGING:-}" ]; then
  [ -n "$log_file" ] || { mkdir -p "$REPO_ROOT/logs"; log_file="$REPO_ROOT/logs/bootstrap-$(date +%Y%m%d-%H%M%S).log"; }
  export _BOOTSTRAP_LOGGING=1
  echo "logging to $log_file"
  exec > >(tee "$log_file") 2>&1
fi

step() { printf '\n=== %s ===\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# 127.0.0.1, never localhost (Docker IPv6 publish black-holes ::1 for ~21s).
DB_URL="postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:${db_port}/cheatsheet"

# ---------------------------------------------------------------- backend ---
if [ "$do_backend" -eq 1 ]; then
  BACKEND_DIR="$REPO_ROOT/backend"
  VENV="$BACKEND_DIR/.venv"
  PY="$VENV/bin/python"

  step 'Backend: virtualenv + dependencies'
  have python3 || { echo 'python3 not on PATH.' >&2; exit 1; }
  if [ ! -x "$PY" ]; then
    echo 'Creating .venv …'; python3 -m venv "$VENV"
  else
    echo '.venv present — reusing.'
  fi
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e "$BACKEND_DIR[dev]"

  if [ "$skip_db" -eq 0 ]; then
    step "Backend: Postgres (host port $db_port)"
    have docker || { echo 'docker not on PATH. Use --skip-db.' >&2; exit 1; }
    export CHEATSHEET_DB_PORT="$db_port"
    (
      cd "$BACKEND_DIR"
      docker compose up -d
      printf 'Waiting for Postgres to accept connections …'
      ready=0
      for _ in $(seq 1 30); do
        if docker compose exec -T db pg_isready -U cheatsheet >/dev/null 2>&1; then ready=1; break; fi
        sleep 1; printf '.'
      done
      printf '\n'
      [ "$ready" -eq 1 ] || { echo 'Postgres did not become ready in 30s.' >&2; exit 1; }

      step 'Backend: migrations + queue schema'
      # Migrations read CS_DATABASE_URL; config default carries no creds.
      export CS_DATABASE_URL="$DB_URL"
      "$PY" scripts/apply_migrations.py
      "$PY" scripts/apply_queue_schema.py
    )
  else
    echo 'Skipping Docker/DB (--skip-db).'
  fi
fi

# --------------------------------------------------------------- frontend ---
if [ "$do_frontend" -eq 1 ]; then
  FRONTEND_DIR="$REPO_ROOT/frontend"
  if [ -f "$FRONTEND_DIR/package.json" ]; then
    step 'Frontend: npm install'
    have npm || { echo 'npm not on PATH. Use --backend to skip frontend.' >&2; exit 1; }
    ( cd "$FRONTEND_DIR" && npm install )
  else
    echo 'No frontend/package.json yet — skipping.'
  fi
fi

# ------------------------------------------------------------------- test ---
if [ "$run_test" -eq 1 ]; then
  if [ "$do_backend" -eq 1 ]; then
    step 'Verify: pytest'
    # DB tests need this; without it they skip (a skip is not a pass). Set BOTH:
    # fixtures read CS_TEST_DATABASE_URL, but the queue test's module-level
    # procrastinate_app singleton is built from CS_DATABASE_URL — leave that
    # unset and it falls back to localhost:5432 and hits any native Postgres.
    if [ "$skip_db" -eq 0 ]; then
      export CS_DATABASE_URL="$DB_URL"
      export CS_TEST_DATABASE_URL="$DB_URL"
    fi
    ( cd "$REPO_ROOT/backend" && .venv/bin/python -m pytest -q )
  fi
  if [ "$do_frontend" -eq 1 ] && [ -f "$REPO_ROOT/frontend/package.json" ]; then
    step 'Verify: npm run build'
    ( cd "$REPO_ROOT/frontend" && npm run build )
  fi
fi

step 'Bootstrap complete'
if [ "$do_backend" -eq 1 ] && [ "$skip_db" -eq 0 ]; then
  echo "DB URL: $DB_URL"
  echo "Run tests later with:"
  echo "  cd backend && . .venv/bin/activate"
  echo "  export CS_DATABASE_URL='$DB_URL'"
  echo "  CS_TEST_DATABASE_URL='$DB_URL' pytest -q"
fi
