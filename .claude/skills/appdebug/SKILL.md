---
name: appdebug
description: Run and debug the CheatSheet dev environment via bootstrap.ps1. Use when the user says "/appdebug", "bootstrap the app", "why won't the backend/DB start", "set up my env", "tests won't connect to the DB", or when a DB/queue test fails with a connection or auth error. Drives bootstrap.ps1's diagnose/auto-repair flags, reads the transcript, and applies the known-trap playbook.
---

# appdebug — run & debug the dev environment

Optional skill. Drives [`bootstrap.ps1`](../../../bootstrap.ps1) (POSIX teammates: `bootstrap.sh`) to bring a checkout to "tests pass" and to diagnose the recurring host traps documented in `backend/CLAUDE.md`. The script is the tool; this skill is how to steer it.

## The one-shot happy path

```powershell
./bootstrap.ps1 -AutoPort -Test
```

`-AutoPort` sidesteps the most common failure without asking. Exit `0` + `RESULT: OK` = done; relay the Summary block. Exit `1` = a step failed; go to the playbook. Every run auto-writes a transcript to `logs/bootstrap-<timestamp>.log` (repo root, git-ignored) — read it when the console tail isn't enough.

## Debug loop (when something fails)

1. **Diagnose first, mutate nothing:**
   ```powershell
   ./bootstrap.ps1 -Diagnose
   ```
   Read the preflight block: tool versions, `.venv` presence, `CS_*` env vars, **host-port ownership**, container publish state. The `[!]` lines are the verdict.
2. **Match the symptom** to the playbook below and re-run with the fixing flag.
3. **Read the transcript** (`logs/bootstrap-<timestamp>.log`, newest) end-to-end if the console tail isn't enough — it captures native `docker`/`pytest` output the summary compresses.
4. The tail is machine-readable: `PASS`/`FAIL` per step, then `RESULT: OK|FAIL` and a matching exit code. Grep that, don't scrape stack traces.

## Known-trap playbook

| Symptom (in output/log) | Cause | Fix |
|---|---|---|
| `[!] host port 5432 owned by NON-Docker 'postgres'` | A **native** Postgres owns the host port; the container's 5432 is unpublished, so connects hit the wrong server. | `-AutoPort` (auto-picks a free port ≥55432), or `-DbPort <free>`. |
| `password authentication failed for user "cheatsheet"` | Either the native-pg trap above, **or** the `cheatsheet_pgdata` volume was first initialized with different creds (`POSTGRES_PASSWORD` only applies on first init of an empty data dir). | First rule out the port trap. If the volume is stale: `cd backend; docker compose down -v; docker compose up -d` (destroys local data), then re-run bootstrap. |
| Queue test hits `localhost:5432 / no password supplied` while others pass | Only `CS_TEST_DATABASE_URL` was set. The queue test's module-level `procrastinate_app` singleton is built from **`CS_DATABASE_URL`**; unset, it falls back to the config default. | `-Test` sets **both** vars. If running pytest by hand, export both. |
| `Postgres did not become ready in 30s` | Container unhealthy or still initializing. | `cd backend; docker compose ps; docker compose logs db`. Re-run once healthy. |
| `docker not on PATH` | Docker Desktop not running / not installed. | Start Docker Desktop, or `-SkipDb` (DB-backed tests then skip — a skip is not a pass). |
| Parse error mentioning `â€"` / mangled chars | Non-ASCII (em-dash) in the `.ps1`; PS 5.1 reads it as ANSI without a BOM. | Keep `bootstrap.ps1` ASCII-only. |

## Flags cheat-sheet

`-Diagnose` preflight only · `-AutoPort` dodge a taken host port · `-DbPort N` pin the host port · `-SkipDb` no Docker/migrations · `-Backend`/`-Frontend` one side only · `-Test` run pytest + `npm run build` · `-LogFile PATH` transcript.

## Rules

- **Never invent a PASS.** Report the actual Summary + exit code. A skipped DB test is not a pass (`backend/CLAUDE.md`).
- **`docker compose down -v` destroys the local dev database.** Only suggest it for the stale-creds case, and say what it deletes before running it.
- **Don't edit the schema or migrations to make a run pass** — the migrations are the locked contract (root `CLAUDE.md §5`). A migration failure is a real bug to surface, not to route around.
- Write temp logs to the session scratchpad, not the repo.
