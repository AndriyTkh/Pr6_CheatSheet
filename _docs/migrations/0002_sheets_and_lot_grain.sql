-- 0002_sheets_and_lot_grain.sql
-- ARCHITECTURE.md rev. 3 — closes the catalog's open decisions.
-- Additive to 0001; 0001 is NOT edited in place (CLAUDE.md §5).
--
-- Lands five things:
--   1. NotApplicable        — 8th cell_status  (§5, §16 #9)
--   2. sheet + row_link     — derived sheets   (§2a, §16 #10)
--   3. lot grain            — row = one tender LOT (§16 #3)
--   4. required/optional    — dead-end lock fires on ANY required input (§3, §6)
--   5. typed list cells + the EXPANSION GATE (§2a, §16 #2):
--        - column.value_type/item_type  — a cell may hold a typed list
--        - column_input.consumes        — whole_list | per_item
--        - row.parent_row_id/depth/ordinal + column.target_depth
--                                       — inline expand (children between rows)
--        - row_link                     — N-ary lineage for deduped/pair children
--      The gate itself (reject per_item -> list column) is APP-side at edge-add,
--      next to the cycle check (§4 step2). It is NOT a cell_status: no cell is
--      created, so there is nothing for the DB to hold.
--
-- Safe on an empty DB (the pilot case) and on a populated one: every existing
-- row/column is backfilled onto one implicit source sheet per case.
--
-- REQUIRES POSTGRES 15+ (no version is pinned in tech-stack-decision.md — pin it
-- there when Railway is provisioned). Two features below need it:
--   * ALTER TYPE ... ADD VALUE inside a transaction   -> PG 12+
--     (the new value may not be USED until this txn commits; nothing here does)
--   * UNIQUE ... NULLS NOT DISTINCT                   -> PG 15+
--     needed because a no-lots tender has lot_id = NULL and must still be
--     unique. On PG <15 replace row_lot_grain_uq with two partial indexes:
--       ... (sheet_id, tender_id, lot_id) WHERE lot_id IS NOT NULL
--       ... (sheet_id, tender_id)         WHERE lot_id IS NULL

BEGIN;

-- =====================================================================
-- 1. ENUMS
-- =====================================================================

-- §5/§16 #9. "Nothing to check here" != "not enough data". Emitters in P0:
-- Pair builder (lot with <2 bidders), YouControl (identifier.scheme != 'UA-EDR').
-- Lock behavior (§6): propagates as ITSELF, never downgraded to InsufficientData.
ALTER TYPE cell_status ADD VALUE IF NOT EXISTS 'NotApplicable' AFTER 'NeedsReview';

-- §2a: rows produced by Unnest/Explode + Pair builder onto a derived sheet.
-- Distinct from 'generated' (§16 #7 = agent-invented rows with no parent cells);
-- a derived row HAS parents and must be visibly different in the grid.
ALTER TYPE row_origin ADD VALUE IF NOT EXISTS 'derived';

CREATE TYPE sheet_kind         AS ENUM ('source', 'derived');            -- §2a
CREATE TYPE row_link_relation  AS ENUM ('expanded_from', 'pair_member'); -- §2a lineage

-- §2a gate. Declared per DAG edge because the SAME recipe may take one column
-- whole and another per-item.
CREATE TYPE input_consumption  AS ENUM ('whole_list', 'per_item');

-- =====================================================================
-- 2. SHEET (§2a — a case is a set of sheets, not one grid)
-- =====================================================================
CREATE TABLE sheet (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id           uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  name              text NOT NULL,
  kind              sheet_kind NOT NULL,
  grain_label       text NOT NULL,          -- 'lot' | 'company' | 'pair' | 'document'
  parent_sheet_id   uuid REFERENCES sheet(id) ON DELETE CASCADE,  -- derived: where it came from
  produced_by_run_id uuid REFERENCES run(id),                      -- derived: the run that built it
  position          integer NOT NULL DEFAULT 0,
  created_at        timestamptz NOT NULL DEFAULT now(),
  -- a source sheet has no parent; a derived sheet must have one (§2a: the DAG
  -- spans sheets at the sheet boundary, so the boundary must be recorded)
  CONSTRAINT sheet_parent_iff_derived CHECK (
    (kind = 'source'  AND parent_sheet_id IS NULL) OR
    (kind = 'derived' AND parent_sheet_id IS NOT NULL)
  )
);
CREATE INDEX sheet_case_idx ON sheet(case_id);

-- =====================================================================
-- 3. ROW / COLUMN -> SHEET
-- Two-step: add nullable, backfill one implicit source sheet per case, then
-- enforce NOT NULL. Keeps the migration re-runnable against existing data.
-- =====================================================================
ALTER TABLE "row"    ADD COLUMN sheet_id uuid REFERENCES sheet(id) ON DELETE CASCADE;
ALTER TABLE "column" ADD COLUMN sheet_id uuid REFERENCES sheet(id) ON DELETE CASCADE;

INSERT INTO sheet (case_id, name, kind, grain_label)
SELECT id, 'Тендери', 'source', 'lot' FROM "case";   -- §16 #11 UI is Ukrainian-only

UPDATE "row" r
   SET sheet_id = s.id
  FROM sheet s
 WHERE s.case_id = r.case_id AND s.kind = 'source' AND r.sheet_id IS NULL;

UPDATE "column" c
   SET sheet_id = s.id
  FROM sheet s
 WHERE s.case_id = c.case_id AND s.kind = 'source' AND c.sheet_id IS NULL;

ALTER TABLE "row"    ALTER COLUMN sheet_id SET NOT NULL;
ALTER TABLE "column" ALTER COLUMN sheet_id SET NOT NULL;

CREATE INDEX row_sheet_idx    ON "row"(sheet_id);
CREATE INDEX column_sheet_idx ON "column"(sheet_id);

-- A column belongs to exactly one sheet; a cell is (row, column) and both must
-- agree. Enforced in APP at column create + cell write (same place as the §4
-- step2 acyclicity check) — a cross-table CHECK is not expressible here without
-- a trigger, and 0001 chose app-level enforcement for the DAG invariant too.

-- =====================================================================
-- 4. ROW_LINK (§2a — derived-row lineage back to its parents)
-- Company row -> each lot it bid on ('exploded_from', N links).
-- Pair row    -> its two member company rows ('pair_member', exactly 2).
-- This is what makes @shared_lots and every pair citation traceable (§9).
-- =====================================================================
CREATE TABLE row_link (
  child_row_id   uuid NOT NULL REFERENCES "row"(id) ON DELETE CASCADE,
  parent_row_id  uuid NOT NULL REFERENCES "row"(id) ON DELETE CASCADE,
  relation       row_link_relation NOT NULL,
  source_cell_row_id    uuid,          -- the list cell this element came from
  source_cell_column_id uuid,          -- (Expand); NULL for pair_member
  source_ordinal        integer,       -- index in that cell's value_jsonb array
                                       -- -> also the index into citation_jsonb (§9),
                                       --    which is how the item's citation reaches
                                       --    the child row
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (child_row_id, parent_row_id, relation),
  CHECK (child_row_id <> parent_row_id),
  FOREIGN KEY (source_cell_row_id, source_cell_column_id)
    REFERENCES cell(row_id, column_id) ON DELETE SET NULL
);
CREATE INDEX row_link_parent_idx ON row_link(parent_row_id, relation);
CREATE INDEX row_link_child_idx  ON row_link(child_row_id);

-- =====================================================================
-- 4b. EXPANSION — tree edge, grain, ordering (§2a, §16 #2)
--
-- TWO lineage mechanisms, on purpose (§16 #2):
--   row.parent_row_id  1:1 TREE  -> grain, sort order, inline rendering
--   row_link           N-ary GRAPH -> evidence + traceability
-- A deduped company in new_table mode bids on 3 lots: parent_row_id CANNOT hold
-- 3 values, so dedup lives in row_link. A pair row has 2 members and no single
-- tree parent -> parent_row_id NULL, two pair_member links.
-- Every expanded child writes BOTH, so downstream code walks one path.
-- =====================================================================
ALTER TABLE "row"
  ADD COLUMN parent_row_id uuid REFERENCES "row"(id) ON DELETE CASCADE,
  ADD COLUMN depth   smallint NOT NULL DEFAULT 0,   -- 0 = source, 1 = expanded child
  ADD COLUMN ordinal integer,                       -- index in the source list; NULL at depth 0
  ADD COLUMN position integer NOT NULL DEFAULT 0,   -- sheet-level display order
  ADD CONSTRAINT row_depth_implies_parent CHECK (
    (depth = 0 AND parent_row_id IS NULL AND ordinal IS NULL) OR
    (depth > 0 AND ordinal IS NOT NULL)
    -- depth>0 with NULL parent_row_id is legal: new_table children (deduped or
    -- not) and pair rows carry lineage in row_link instead.
  ),
  ADD CONSTRAINT row_no_self_parent CHECK (parent_row_id IS DISTINCT FROM id);

-- inline render band: a parent's children in list order, adjacent to the parent
CREATE INDEX row_parent_ordinal_idx ON "row"(parent_row_id, ordinal)
  WHERE parent_row_id IS NOT NULL;
CREATE INDEX row_sheet_position_idx ON "row"(sheet_id, position);

-- §2a: a column runs on ONE grain. The wavefront (§4 step5) creates cells only
-- for rows at this depth, so an inline-expanded sheet's two grains never cross
-- and "run YouControl on participants" cannot fire on lot rows.
ALTER TABLE "column"
  ADD COLUMN target_depth smallint NOT NULL DEFAULT 0;

-- §2a typed list cells. value_type is the column's declared shape; item_type is
-- set ONLY when value_type='list' and the list is typed (untyped list = NULL,
-- still citable, but Formula/Compute and typed expansion refuse it).
-- 0001 already has column.value_type as free text; constrain the list case only.
ALTER TABLE "column"
  ADD COLUMN item_type text,
  ADD CONSTRAINT column_item_type_only_for_list CHECK (
    item_type IS NULL OR value_type = 'list'
  );

-- =====================================================================
-- 5. LOT GRAIN (§16 #3)
-- row.provenance_jsonb is re-keyed from {tenderID} to {tenderID, lotID}.
-- lotID is NULL for a tender with no lots[] — still exactly one row (§6a).
-- Generated columns give the connector a stable, indexable dedup key without
-- duplicating the ids outside the provenance blob.
-- =====================================================================
ALTER TABLE "row"
  ADD COLUMN tender_id text GENERATED ALWAYS AS (provenance_jsonb ->> 'tenderID') STORED,
  ADD COLUMN lot_id    text GENERATED ALWAYS AS (provenance_jsonb ->> 'lotID')    STORED;

-- One row per (sheet, tender, lot). NULLS NOT DISTINCT so a no-lots tender
-- cannot be inserted twice (PG 15+). Partial: only rows that carry a tenderID,
-- so derived/upload/generated rows are unaffected.
CREATE UNIQUE INDEX row_lot_grain_uq
  ON "row"(sheet_id, tender_id, lot_id) NULLS NOT DISTINCT
  WHERE tender_id IS NOT NULL;

-- =====================================================================
-- 6. REQUIRED / OPTIONAL INPUTS (§3, §6 dead-end lock)
-- The lock must fire when ANY *required* input is terminal-empty. Without this
-- flag the engine cannot tell "guaranteed InsufficientData, don't dispatch"
-- from "degraded but worth running" — and burns the LLM call either way.
-- Default true = existing edges keep the strictest (cheapest) behavior.
-- =====================================================================
ALTER TABLE column_input
  ADD COLUMN is_required boolean NOT NULL DEFAULT true;

-- =====================================================================
-- 7. THE LIST GATE (§2a, §16 #2)
-- per_item + a list column -> the add-column action is REJECTED at edge-add,
-- app-side, next to the cycle check (§4 step2). Enforced there and not here
-- because it must fail while the user is COMPOSING the column: no cell exists
-- yet, nothing is enqueued, nothing is spent, and the error can offer the two
-- Expand modes. A DB constraint would only be reachable after the row landed.
-- Default whole_list = existing edges keep working (they predate lists).
-- =====================================================================
ALTER TABLE column_input
  ADD COLUMN consumes input_consumption NOT NULL DEFAULT 'whole_list';

COMMIT;

-- =====================================================================
-- APP-SIDE INVARIANTS this migration deliberately does NOT encode
-- (all need cross-table state; 0001 already put the DAG acyclicity check in the
--  app for the same reason):
--   * list gate: column_input.consumes='per_item' -> input column must not be
--     a list. Checked at edge-add (§4 step2).
--   * a cell's row.sheet_id must equal its column.sheet_id.
--   * a cell exists only where row.depth = column.target_depth (§4 step5).
--   * child.sheet_id = parent.sheet_id for inline expand; differs for new_table.
--
-- NOT in this migration, deliberately:
--   * cross_row_result is UNCHANGED. Its scope narrows (§8: no-row-shape
--     signals only) but that is a usage rule, not a schema change.
--   * Merge / row_state / terminal_scope / 'Rejected' stay DORMANT (§5).
--   * ANN index on chunk.embedding still week 2 (0001 note).
-- =====================================================================
