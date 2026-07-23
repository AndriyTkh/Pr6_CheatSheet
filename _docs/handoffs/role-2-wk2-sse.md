# role-2/wk2-sse — SSE streaming with batched flush

Task: `_docs/tasks/role-2.md` week 2, "SSE streaming with batched flush" (§4 step 7).
Status at handoff: `REVIEW`. Verify green (`pytest app/tests/test_sse.py -q` → **14
passed**), full suite **149 passed, 0 skipped, 0 failed** against the dev
`cheatsheet` database (`CS_TEST_DATABASE_URL` + `CS_DATABASE_URL` both set to it).

## What landed

All under `backend/app/realtime/`:

| File | Owns |
|---|---|
| `events.py` | `CellUpdate` — the wire shape. Carries the monotonic `version`. |
| `batcher.py` | `CellBatcher` — the coalescing flush buffer. **The core of the task.** |
| `broker.py` | `Broker` + process-wide `broker` — in-process fan-out, scoped by case. |
| `listener.py` | `run_listener()` + `_resolve_update()` — bridges the pg `NOTIFY` into the broker. |
| `routes.py` | `GET /case/{case_id}/stream` — the SSE endpoint (`EventSourceResponse`). |

Wiring: `api/routes/__init__.py` includes the realtime router; `main.py` lifespan
starts one `run_listener()` task per web process and cancels it on shutdown.
`app/tests/test_sse.py` is new.

Nothing in `services/`, `tasks/`, or the models changed — the SSE layer consumes
the wavefront's existing `publish_cell_terminal()` seam and touches nothing it owns.

## The event shape (for Role 5)

One coalesced flush = one SSE `cells` event. **Never one event per cell** — that is
the whole task.

```
event: cells
id: 5187
data: {"updates": [
         {"row_id": "…", "column_id": "…", "version": 5183, "status": "Answered"},
         {"row_id": "…", "column_id": "…", "version": 5187, "status": "NotFound"}
       ],
       "max_version": 5187}
```

* Each entry addresses a cell by `(row_id, column_id)` and carries its terminal
  `status` (a §5 enum value: `Answered`, `NotFound`, `NotApplicable`, …) and its
  `version`. The grid re-reads nothing on a normal update — apply it in place.
* `data.max_version` and the SSE `id:` are the same number: the batch's high-water
  version. The browser resends `id:` as `Last-Event-ID` on reconnect.
* Subscribe with the native `EventSource` (or a fetch reader). URL:
  `GET /case/{case_id}/stream`. It streams until the client disconnects; a comment
  ping every 15s keeps proxies from reaping an idle connection between bursts.

**Coalescing means a burst re-renders the grid once, not thousands of times.** At
pilot ceiling (~10-15k cells/case) a wavefront run turns cells terminal in a burst;
the batcher collects every cell that went terminal inside one window (default
200ms, `DEFAULT_WINDOW_SECONDS`) or once 200 cells queue (`DEFAULT_MAX_CELLS`),
whichever comes first, and ships them as one message. Two updates to the same cell
inside one window collapse to one entry at the **higher** version.

## Version semantics (for the reconcile-on-reconnect task)

The next task (`GET /case/:id/cells?since=<version>`) depends on exactly two
properties this task nails down, so build against these, don't retrofit:

1. **`version` is `cell.version` — `cell_version_seq`, strictly monotonic across
   every terminal write.** The wavefront branch already bumps it on the real-run
   path, the cache-hit path, `_fail`, and the `blocked → pending` promotion (see
   `role-2-wk2-wavefront.md`). The SSE layer never invents a version; it reports
   what it read.
2. **Cells are addressable by `(row_id, column_id)` and the version only ever
   increases per cell.** Coalescing keeps the max, never a lower value, so a number
   the client saw never goes backwards.

**The reconnect contract is exactly what §4 step 7 spells out:** the live stream
has *no replay of its own* and deliberately drops on overload (see below). On
reconnect the client reads its `Last-Event-ID` (= the last `max_version` it saw),
calls `GET /case/:id/cells?since=<that version>` to catch up, then resumes the
stream. `?since` must return every cell with `version > since` for the case,
ordered by `version`, so the cursor advances monotonically. Because every write
bumps the seq, the reconcile fetch and the live stream page the *same* number line
— no cell filled during a disconnect is lost.

## Design seams and why

* **The listener re-reads; it never trusts the NOTIFY body.** `publish_cell_terminal`
  emits `{"row_id","column_id"}` only (wavefront handoff: 8000-byte limit, and a
  body written by one worker is stale for another). `_resolve_update()` reads the
  cell for the authoritative `version`/`status` and resolves `case_id` off
  `row.case_id`. A cell that is missing or non-terminal at read time is dropped —
  the read is the authority, not the payload.
* **The broker drops overflow, it never blocks.** A slow/paused client fills its
  bounded queue (`SUBSCRIBER_QUEUE_MAX = 2000`); further updates are dropped with a
  log line, not queued unboundedly and not blocking the single listener that feeds
  every connection. This is safe **only because** the reconcile endpoint exists —
  a dropped live message is recovered by `?since=`. If reconcile slips, this
  becomes real data loss; keep them together.
* **One listener per web process, self-reconnecting.** Postgres `NOTIFY` fans out to
  every `LISTEN`er, so each process feeds its own subscribers. The listener retries
  a down DB every 2s, so the app boots even if Postgres is not yet up.

## Spec ambiguity — flagged, not buried

* **§4 step 7 fixes the *policy* ("every 150-250ms or N cells") but not the flush
  *shape*.** Resolved: flush is time-**or**-size, whichever fires first
  (`window_seconds` OR `max_cells`); the window clock starts on the first update of
  a burst, not on a fixed tick, so an idle stream emits nothing rather than a
  stream of empty heartbeats. Coalescing key is the cell identity, tie-broken by
  version. All four choices are asserted in `test_sse.py`; if the team wants a
  fixed-tick flush instead, `CellBatcher.batches()` is the one place to change.
* **The endpoint path.** Chose `GET /case/{case_id}/stream` to sit beside the
  reconcile task's `GET /case/{case_id}/cells?since=`. Not spelled out in §4; if the
  API-routes task wants a different prefix (e.g. under `/api`), move both together.

## Environment notes

* The three DB-backed tests (`_resolve_update`) need `CS_TEST_DATABASE_URL`; they
  skip silently without it and a skip is not a pass (`backend/CLAUDE.md`). The 11
  pure tests — including the load-bearing "burst → one message" assertion — run with
  no database.
* `127.0.0.1`, never `localhost` (`backend/CLAUDE.md`).
* `run_listener()` needs `asyncpg` (already the SQLAlchemy driver) and opens its own
  raw connection for `LISTEN` — asyncpg cannot `LISTEN` on a pooled SQLAlchemy
  connection, so this is deliberate, not a duplicate pool.
