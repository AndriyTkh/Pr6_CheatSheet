# CheatSheet

A **columnar, lineage-tracked compute graph over rows** — a spreadsheet on the
surface, a build-system/DAG engine underneath — piloted over Prozorro +
YouControl. Backend: FastAPI + SQLAlchemy(asyncpg) + Postgres 16 + Procrastinate.
Frontend: React + Vite + TanStack Table.

> **Contributors:** read [`CLAUDE.md`](CLAUDE.md) first — it is the map (docs,
> task tracking, git rules). This file is only how to stand the app up locally.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | backend venv |
| Node + npm | 18+ (22 tested) | frontend |
| Docker Desktop | any recent | local Postgres 16 (pgvector image) |
| PowerShell | 5.1+ | Windows: the primary bootstrap. POSIX: use `bootstrap.sh`. |

---

## Quick start

One script sets up **everything** — backend venv + deps, local Postgres,
migrations + queue schema, frontend deps — and (with `-Test`) runs the full
verification. Idempotent; safe to re-run.

**Windows (PowerShell):**
```powershell
./bootstrap.ps1 -AutoPort -Test
```

**macOS / Linux:**
```bash
./bootstrap.sh --test
```

Green `RESULT: OK` (exit 0) means the checkout is ready. Every run writes a
transcript to `logs/bootstrap-<timestamp>.log` (git-ignored; `-NoLog` /
`--no-log` to disable).

> **Why `-AutoPort`?** If a *native* Postgres already owns host port 5432, the
> Docker container's port can't be reached there and connects silently hit the
> wrong server (auth failure). `-AutoPort` detects this and publishes on a free
> port (≥55432) instead. Without a native Postgres you can omit it.

---

## What bootstrap does

1. **Backend deps** — creates `backend/.venv` (reused if present), `pip install -e .[dev]`.
2. **Database** — `docker compose up -d` (Postgres 16 + pgcrypto/vector), waits for health.
3. **Migrations** — applies `_docs/migrations/0001…`, `0002…`, then Procrastinate's queue schema.
4. **Frontend deps** — `npm install` in `frontend/`.
5. **Verify** (`-Test` / `--test`) — `pytest -q` (183 tests) + `npm run build`.

### Flags

| PowerShell | POSIX | Effect |
|---|---|---|
| `-Backend` / `-Frontend` | `--backend` / `--frontend` | one side only (default: both) |
| `-SkipDb` | `--skip-db` | no Docker/migrations (DB-backed tests then **skip**) |
| `-DbPort N` | `--db-port N` | pin the host port for Postgres |
| `-AutoPort` | — | auto-dodge a taken host port (Windows) |
| `-Test` | `--test` | run pytest + `npm run build` after setup |
| `-Diagnose` | — | preflight diagnostics only, change nothing |
| `-LogFile PATH` / `-NoLog` | `--log-file PATH` / `--no-log` | transcript path / disable |

---

## Running things after setup

**Backend tests** — both env vars must point at the DB (the queue test's
Procrastinate app is built from `CS_DATABASE_URL`; the fixtures read
`CS_TEST_DATABASE_URL`). Use `127.0.0.1`, never `localhost`:

```powershell
cd backend; .venv\Scripts\Activate.ps1
$env:CS_DATABASE_URL      = 'postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:55432/cheatsheet'
$env:CS_TEST_DATABASE_URL = $env:CS_DATABASE_URL
pytest -q
```
(Swap `55432` for `5432` if bootstrap did not remap the port.)

**Frontend dev server:**
```bash
cd frontend && npm run dev      # vite; npm run build is the Verify line
```

---

## Troubleshooting

Run the diagnostics — it reports tool versions, host-port ownership, container
state, and the `CS_*` env vars without changing anything:

```powershell
./bootstrap.ps1 -Diagnose
```

Coding agents: the **`/appdebug`** skill drives this and applies the known-trap
playbook (see [`.claude/skills/appdebug/SKILL.md`](.claude/skills/appdebug/SKILL.md)).

| Symptom | Fix |
|---|---|
| `password authentication failed for user "cheatsheet"` | Native Postgres owns 5432 → re-run with `-AutoPort` / `--db-port 55432`. If the DB *volume* has stale creds: `cd backend && docker compose down -v && docker compose up -d` (**deletes local data**), then re-bootstrap. |
| Queue test alone fails on `localhost:5432` | Only one env var set — export **both** `CS_DATABASE_URL` and `CS_TEST_DATABASE_URL`. |
| `Postgres did not become ready` | `cd backend && docker compose ps && docker compose logs db`. |
| `docker not on PATH` | Start Docker Desktop, or `-SkipDb` (DB tests skip — a skip is not a pass). |

Host traps in depth: [`backend/CLAUDE.md`](backend/CLAUDE.md) ("Run it").

---

## Layout

| Path | What |
|---|---|
| `backend/` | FastAPI app, DAG engine, recipes, connectors, queue ([`backend/CLAUDE.md`](backend/CLAUDE.md)) |
| `frontend/` | React + Vite grid ([`frontend/CLAUDE.md`](frontend/CLAUDE.md)) |
| `_docs/` | Architecture contract, tasks, migrations ([`CLAUDE.md`](CLAUDE.md) is the index) |
| `bootstrap.ps1` / `bootstrap.sh` | This setup, Windows / POSIX |
