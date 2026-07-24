# role-2/wk1-models-recipe-dag — handoff

## 2026-07-23 @andriy (agent session)

- **Landed:** week 1 closes. Models mirror `0001`+`0002`, `recipes/base.py`, Prozorro
  connector at lot grain, DAG cycle/list-gate/topo + the §2 invariants 2–4, and
  `services/row_ingest.py` running the loop end to end. Verify: `pytest app/tests -q`
  with `CS_TEST_DATABASE_URL` set → **80 passed, 0 skipped**. Gate proof is a *live*
  run, not the suite: `scripts/gate_week1.py --tender-id 59ac5ae6011344c88153399786b0c78e`
  → 1 lot row, 5 cells all `Answered` with citations, winner `31200334`, 785510 UAH,
  3 participants. Second run says "0 created, 1 updated" — idempotent on
  `(tenderID, lotID)` (§16 #3).
- **Environment, the part that eats sessions:** connect on **`127.0.0.1`, never
  `localhost`** — `localhost` resolves `::1` first and Docker's IPv6 publish
  black-holes it ~21s per connect, so the suite looks hung rather than broken. Native
  Postgres owns 5432 here, so compose publishes `${CHEATSHEET_DB_PORT:-5432}:5432` and
  this machine runs `55432`. Both now in `backend/CLAUDE.md`. Also: pipe a long run to
  a file, don't `| tail` — tail buffers to EOF and you watch a blank screen.
- **Dead ends:** the ascending `/tenders` feed starts in **2015** — scanning it for a
  present-day tender is a decade of replay. Hence `feed(descending=True)`. It is
  deliberately *not* wired into sync: a resumed descending cursor silently drops
  everything published while you were away, so sync stays ascending-by-`dateModified`
  (§6a). Early records are also mostly `unsuccessful` with no awards, so a scan that
  finds "a tender" often finds one that exercises almost none of the extraction —
  `find_awarded_tender` filters for lots + bids + an active award.
- **Spec friction:** none in §2/§2a/§4/§6a — the contract held as written. One doc bug:
  the app-skeleton task's Verify named `app/tests/test_health.py`, which didn't exist.
  Written this PR (liveness answers with no DB; no setting resolves to a hardcoded
  secret, with a name-shaped backstop so a new `*_api_key` field fails until checked).
- **Still blocked:** YouControl connector, on Role 1's key **and** the module/license
  confirmation. Don't start it on the key alone — which metered modules the license
  covers decides what the recipes may assume.
- **Next:** week 2 in task order — Procrastinate wiring (`tasks/`), then wavefront-gated
  enqueue + `cache_key` (§4 steps 5–6, depth-aware). **Consider pulling the grid API
  routes ahead of SSE** if Role 5 is idle: that task is what Role 5's non-mocked
  integration blocks on, and SSE has no dependent waiting on it.
