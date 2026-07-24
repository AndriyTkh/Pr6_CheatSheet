# role-2/wk2-reconcile — Reconcile-on-reconnect endpoint

Task: `_docs/tasks/role-2.md` week 2, "Reconcile-on-reconnect endpoint" (§4 step 7).
Status at handoff: `REVIEW`. Verify green (`pytest app/tests/test_reconcile.py -q` →
**9 passed**), full suite **158 passed, 0 skipped, 0 failed** against the dev
`cheatsheet` database (`CS_TEST_DATABASE_URL` + `CS_DATABASE_URL` both set).

Builds directly on the SSE task's version semantics — read `role-2-wk2-sse.md`
first; this file assumes it.

## What landed

| File | Owns |
|---|---|
| `services/reconcile.py` | `fetch_cells_since()` + `ReconciledCell` — the query and its wire shape. |
| `api/routes/reconcile.py` | `GET /case/{case_id}/cells?since=` — the HTTP endpoint. |
| `api/routes/__init__.py` | Includes the new router (one line). |
| `app/tests/test_reconcile.py` | New. The Verify assertion + corners. |

Nothing else changed. The endpoint is a pure read over the existing `cell`/`row`
tables — it consumes the monotonic `cell.version` the wavefront already writes and
the SSE layer already streams; it touches no model, no queue, no realtime code.

## The reconnect handshake, end to end (for Role 5)

The client half is two moving parts: a live `EventSource` on the stream, and one
plain `fetch` on this endpoint whenever the stream reconnects. The cursor that ties
them together is the SSE `id:` (= batch `max_version` = `cell.version`).

```
  ┌─ live: GET /case/{id}/stream ──────────────────────────────┐
  │   event: cells                                             │
  │   id: 5187          ← client stores this as its cursor     │
  │   data: {"updates":[…], "max_version":5187}                │
  └────────────────────────────────────────────────────────────┘
             ✗ connection drops (wifi, laptop sleep, proxy reap)
             … cells 5188…5240 fill on the server while away …
             … the live stream dropped them: it has NO replay …

  ┌─ reconnect step 1 — CATCH UP (this endpoint) ──────────────┐
  │   GET /case/{id}/cells?since=5187                          │
  │   → {"since":5187,                                         │
  │      "max_version":5240,                                   │
  │      "updates":[ {sheet_id,row_id,column_id,               │
  │                   version,status}, … ]}   ← 5188…5240      │
  │   client applies each update in place, advances cursor→5240│
  └────────────────────────────────────────────────────────────┘

  ┌─ reconnect step 2 — RESUME live ───────────────────────────┐
  │   GET /case/{id}/stream   (EventSource reopens)            │
  │   from here the stream carries 5241+                       │
  └────────────────────────────────────────────────────────────┘
```

Order matters: **catch up, then resume.** If you reopen the stream first you can
still miss the sliver that fills between the two calls — but you won't lose it,
because the next reconnect's `?since=` re-covers any gap. The safe, simple client
is: on `EventSource.onerror`/close, `fetch(?since=<cursor>)`, apply, set
cursor = `max_version`, then reopen the stream. The native `EventSource` also
resends the last `id:` as the `Last-Event-ID` request header — you may use that as
your cursor source of truth instead of tracking it in JS.

### Request

`GET /case/{case_id}/cells?since=<int>`

* `since` — the last `cell.version` you saw (your cursor). Optional, defaults `0`;
  `since=0` returns the **whole** case (a fresh client with no cursor catches up on
  everything). Must be `>= 0` (422 otherwise).

### Response (`200`)

```json
{
  "since": 5187,
  "max_version": 5240,
  "updates": [
    {"sheet_id":"…","row_id":"…","column_id":"…","version":5188,"status":"Answered"},
    {"sheet_id":"…","row_id":"…","column_id":"…","version":5240,"status":"NotFound"}
  ]
}
```

* `updates` — every terminal cell in the case with `version > since`, **ordered by
  version ascending**. Apply in place by `(row_id, column_id)`, exactly like an SSE
  `cells` update.
* Each entry is a **superset of the SSE `CellUpdate` shape**: same
  `row_id/column_id/version/status`, **plus `sheet_id`**. The extra field lets you
  route a cell that filled on a sheet you had not loaded before the disconnect —
  e.g. an Expand `new_table` created a whole derived sheet while you were away. On
  the live stream you already have every sheet loaded, so the stream omits it; here
  you may not, so it's included.
* `max_version` — your **new cursor**: the highest version returned, or `since`
  unchanged when nothing advanced (empty `updates`). It never rewinds. Carry it
  into the resumed stream.

## Why this is the whole safety story

The SSE handoff's broker **drops overflow instead of blocking** — deliberately, and
noted there as "safe *only because* the reconcile endpoint exists." This is that
endpoint. A dropped live message is not data loss because the same cell, at the
same monotonic version, is re-served here on the next reconnect. The stream and the
reconcile fetch page the **identical** `cell_version_seq` number line, so:

* **terminal cells only.** The stream carries nothing but terminal cells (the
  listener drops non-terminal reads), so reconcile filters to `TERMINAL` too. If it
  returned `blocked`/`running` cells the client would apply updates the stream never
  sends and the two would disagree. A cell mid-flight is simply picked up later,
  when it goes terminal, via whichever path is live then.
* **monotonic, never backwards.** Every terminal write bumps the seq; coalescing on
  the stream keeps the max. `?since=` returns strictly `version > since` ascending,
  so the cursor only advances. A re-run of an already-seen cell gets a *new* version
  above the cursor and is correctly re-served (tested).

## Design seams and why

* **Scope is the whole case, across every sheet (§2a).** The grid routes will scope
  reads by `sheet_id`; reconnect does not — it catches the entire case up in one
  fetch (`row.case_id`), then hands you `sheet_id` per cell to fan back out. One
  round trip on reconnect beats one-per-open-sheet, and it covers sheets you didn't
  know existed yet.
* **The query joins `cell → row` for `case_id` and `sheet_id`.** `cell` has neither
  column directly (it's `(row_id, column_id)`); both live on `row`. Same resolution
  the SSE listener's `_resolve_update` does (`Row.case_id`), kept consistent.
* **No case-existence 404.** An unknown or empty case returns `{updates: [],
  max_version: since}`, not a 404 — reconcile is about *cells*, and "nothing filled"
  is a valid answer a reconnecting client must handle anyway. Auth/membership is not
  wired yet (no `fastapi-users` dependency on any route this week); when the
  API-routes task adds it, this endpoint takes the same case-scoped guard as the
  grid routes — flagged below.

## Spec friction — flagged, not buried

* **The `role-2/wk2-sse` *branch* does not contain the SSE code.** The realtime/
  layer this task depends on (`backend/app/realtime/`) was committed onto
  `role-2/wk2-chained-columns`, not onto `role-2/wk2-sse` — that branch's tip
  (`0f81244`) is the *queue* commit and has no `realtime/` dir at all. So I branched
  `role-2/wk2-reconcile` off the current HEAD (chained-columns), the only base that
  actually carries the SSE layer. Consequence for whoever merges: the SSE work rides
  in on the chained-columns / this branch lineage, not on the `wk2-sse` branch label.
  Worth reconciling the branch labels before the week-2 PRs land.
* **`?since=` shape not spelled out in §4 beyond the URL.** Resolved: response is an
  envelope `{since, max_version, updates[]}` mirroring the SSE `cells` event so the
  client's apply logic is shared, with `sheet_id` added per entry (justified above).
  If the API-routes task wants a different envelope (e.g. bare array, or an `/api`
  prefix), `api/routes/reconcile.py` is the one place to change — move it together
  with the stream route, they're a pair.
* **Endpoint path.** `GET /case/{case_id}/cells`, sibling to the SSE
  `GET /case/{case_id}/stream`. Same friction the SSE handoff noted: if the grid
  routes land under a prefix, move both.

## Environment notes

* All 9 tests except the route-registration check are DB-backed (`requires_db`) and
  need `CS_TEST_DATABASE_URL`; they **skip silently** without it and a skip is not a
  pass (`backend/CLAUDE.md`). Set it before claiming this verified.
* Postgres in docker `backend-db-1`, host port **55432**. `127.0.0.1`, never
  `localhost` (`backend/CLAUDE.md`).
* Verify run:
  `CS_TEST_DATABASE_URL=postgresql+asyncpg://cheatsheet:cheatsheet@127.0.0.1:55432/cheatsheet pytest app/tests/test_reconcile.py -q`
  → **9 passed**. Full suite same URL → **158 passed, 0 skipped**.
