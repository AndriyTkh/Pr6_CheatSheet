"""§4 step 7 — the realtime layer: cell updates streamed to the grid, coalesced.

The whole point of this package is **update rate**, not row count. At pilot
ceiling (~10-15k cells/case) a wavefront run turns terminal cells in a burst;
one SSE message per cell would re-render the grid thousands of times in a few
seconds. So updates are batched: a flush carries every cell that went terminal
inside one window (150-250ms) or once N cells have queued, whichever comes first
— one message, not N.

Four pieces, one direction of flow:

* `events.CellUpdate` — the wire shape. Carries the cell's **monotonic version**
  (`cell_version_seq`), which is what the reconcile-on-reconnect task pages on.
* `broker.Broker` — in-process fan-out. One process runs the Postgres listener;
  every open SSE connection subscribes to the broker and is scoped to its case.
* `batcher.CellBatcher` — the coalescing buffer. Pure, timing-driven, DB-free —
  this is where "N updates → one message" actually happens, and where the
  Verify test bites.
* `listener` — bridges the `cheatsheet_cell` `NOTIFY` (emitted by
  `publish_cell_terminal`, out-of-process workers) into the broker, re-reading
  the cell for its authoritative version rather than trusting the tiny payload.
"""
