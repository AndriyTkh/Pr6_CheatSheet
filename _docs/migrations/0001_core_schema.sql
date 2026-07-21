-- 0001_core_schema.sql
-- CheatSheet core schema — Day 1-2 joint lock-in (ARCHITECTURE.md §2).
-- "Get migration committed even if empty of data" (parallel-task-list §0.2).
-- This file is the frozen contract the 4 tracks build against. Change only by
-- team agreement + a new numbered migration, never by editing this one in place.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector (§10 embeddings, §7 retrieve)

-- =====================================================================
-- ENUMS
-- =====================================================================

-- §5 typed cell status. ONE enum spanning non-terminal lifecycle + terminal.
-- Plan §4: "blocked -> pending -> running -> <terminal enum>". This is
-- DATA/DISPLAY, never the lock target (Procrastinate owns the job, §4).
CREATE TYPE cell_status AS ENUM (
  -- non-terminal lifecycle
  'blocked', 'pending', 'running',
  -- terminal — P0 active set (owner brief §6, plan §5 — the seven)
  'Answered', 'InsufficientData', 'NotFound', 'SourceUnavailable',
  'ConflictingEvidence', 'Error', 'NeedsReview',
  -- terminal — DORMANT (§5/§8): emitted only by deferred Merge / row-gating
  'Rejected'
);

-- §5 column.status is a ROLLUP derived from cells, not a second source of truth.
CREATE TYPE column_status AS ENUM ('pending', 'running', 'partial', 'done', 'stale');

CREATE TYPE recipe_exec_type AS ENUM ('func', 'agent');           -- §3
CREATE TYPE recipe_shape     AS ENUM ('cell', 'row', 'cross_row'); -- §6 three shapes
CREATE TYPE row_origin       AS ENUM ('connector', 'upload', 'generated'); -- §16 #7
CREATE TYPE row_state        AS ENUM ('active', 'merged');   -- DORMANT axis; P0 always 'active' (§5)
CREATE TYPE terminal_scope   AS ENUM ('cell', 'row');        -- DORMANT; P0 always 'cell' (§5)
CREATE TYPE case_role        AS ENUM ('owner', 'editor', 'viewer'); -- §11 (reviewer = Stretch)

-- =====================================================================
-- CASE + MEMBERSHIP (§11 private by default)
-- =====================================================================
CREATE TABLE "case" (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  owner_id   uuid NOT NULL,                       -- fastapi-users owns the user table (§15)
  is_private boolean NOT NULL DEFAULT true,        -- §11
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE case_member (
  case_id uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  user_id uuid NOT NULL,
  role    case_role NOT NULL,
  PRIMARY KEY (case_id, user_id)
);

-- =====================================================================
-- RECIPE (versioned; §3 interface, §6 catalog)
-- (recipe_id, version) is the identity — old results stay linked to the exact
-- version that produced them (rough-outline #2). Never mutate a shipped version.
-- =====================================================================
CREATE TABLE recipe (
  id            uuid    NOT NULL DEFAULT gen_random_uuid(),
  version       integer NOT NULL,
  name          text    NOT NULL,
  exec_type     recipe_exec_type NOT NULL,   -- func = deterministic, agent = tool loop (§3)
  shape         recipe_shape     NOT NULL,   -- cell-producing | row-producing | cross-row (§6)
  volatile      boolean NOT NULL DEFAULT false, -- §4 step6: agent/web/LLM never re-query on identical inputs
  params_schema jsonb   NOT NULL,            -- typed JSON Schema (§3 params)
  output_schema jsonb   NOT NULL,            -- JSON Schema, ENFORCED at model edge server-side (§3)
  cite_spec     jsonb   NOT NULL DEFAULT '{}', -- how each value anchors (§3/§9)
  eval_spec     jsonb   NOT NULL DEFAULT '{}', -- which metrics apply (§3/§12)
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id, version)
);

-- =====================================================================
-- ROW  (§16 #3: logical row = ONE Prozorro tender package, tender grain)
-- =====================================================================
CREATE TABLE "row" (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id             uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  origin              row_origin NOT NULL,
  provenance_jsonb    jsonb NOT NULL DEFAULT '{}', -- stable IDs + source; Prozorro row keyed by tenderID (§16 #3)
  generated_by_run_id uuid,                        -- §16 #7: set iff origin='generated' (FK added below)
  state               row_state NOT NULL DEFAULT 'active',     -- DORMANT (§5)
  merged_into_row_id  uuid REFERENCES "row"(id),               -- DORMANT: deferred Merge (§8)
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX row_case_idx ON "row"(case_id);

-- =====================================================================
-- COLUMN + EDGES (the DAG; §4)
-- =====================================================================
CREATE TABLE "column" (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id        uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  name           text NOT NULL,
  value_type     text NOT NULL,                 -- display/type hint aligned to output_schema slot
  recipe_id      uuid,                           -- NULL for source/seed (connector/upload) columns
  recipe_version integer,
  output_slot    text NOT NULL DEFAULT '0',      -- §4 step6: which output of a 1->M recipe (anti-collision)
  params_jsonb   jsonb NOT NULL DEFAULT '{}',
  output_lang    text,                           -- §6 output language
  status         column_status NOT NULL DEFAULT 'pending',  -- rollup (§5)
  position       integer NOT NULL DEFAULT 0,
  created_at     timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (recipe_id, recipe_version) REFERENCES recipe(id, version)
);
CREATE INDEX column_case_idx ON "column"(case_id);

CREATE TABLE column_input (
  column_id       uuid NOT NULL REFERENCES "column"(id) ON DELETE CASCADE,
  input_column_id uuid NOT NULL REFERENCES "column"(id) ON DELETE CASCADE,
  PRIMARY KEY (column_id, input_column_id)
  -- Acyclicity enforced in APP at edge-add (DFS/Kahn, §4 step2).
  -- Staleness/lineage walked by recursive CTE over this table (§4).
);

-- =====================================================================
-- RUN (execution log; §10 provenance)
-- =====================================================================
CREATE TABLE run (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipe_id         uuid    NOT NULL,
  recipe_version    integer NOT NULL,
  model_id          text,                         -- pinned concrete id, no floating auto/latest (§10)
  provider_endpoint text,
  prompt_hash       text,
  params_jsonb      jsonb NOT NULL DEFAULT '{}',
  used_fallback     boolean NOT NULL DEFAULT false, -- §10: fallback cells NOT cached (cache_key left NULL)
  cache_bust        boolean NOT NULL DEFAULT false, -- §4 step6 force-refresh
  cost_usd          numeric(12,6),
  status            text NOT NULL DEFAULT 'ok',      -- ok | error
  created_at        timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (recipe_id, recipe_version) REFERENCES recipe(id, version)
);

-- deferred FK: row.generated_by_run_id -> run.id (run defined after row)
ALTER TABLE "row"
  ADD CONSTRAINT row_generated_by_run_fk
  FOREIGN KEY (generated_by_run_id) REFERENCES run(id);

-- =====================================================================
-- CELL  (row x column intersection; the memoized result)
--
-- cache_key (§4 step6) is APP-COMPUTED at dispatch (needs resolved input hashes):
--   cache_key = hash(recipe_version
--                    + resolved_input_hashes   -- hash of each input cell value
--                    + params
--                    + model_id
--                    + output_slot)            -- keeps 1->M outputs from colliding
--   NULL cache_key = non-hittable: fallback runs (§10) and force-refresh (§4 step6).
--   Terminal-empty results are NEGATIVE-cached on this key (dead-end lock, §6).
-- =====================================================================
CREATE SEQUENCE cell_version_seq;   -- monotonic stream version for SSE ?since= reconcile (§4 step7)

CREATE TABLE cell (
  row_id         uuid NOT NULL REFERENCES "row"(id) ON DELETE CASCADE,
  column_id      uuid NOT NULL REFERENCES "column"(id) ON DELETE CASCADE,
  value_jsonb    jsonb,                                  -- MAY be a list (list-in-cell, §16 #2)
  status         cell_status NOT NULL DEFAULT 'blocked',
  citation_jsonb jsonb NOT NULL DEFAULT '[]',            -- ARRAY aligned to value items (§9)
  terminal_scope terminal_scope NOT NULL DEFAULT 'cell', -- DORMANT (§5)
  cache_key      text,                                    -- see block above; NULL = non-hittable
  run_id         uuid REFERENCES run(id),
  version        bigint NOT NULL DEFAULT nextval('cell_version_seq'), -- app bumps on every write
  updated_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (row_id, column_id)
);
CREATE INDEX cell_col_status_idx ON cell(column_id, status);  -- wavefront re-check + rollup (§4/§5)
CREATE INDEX cell_cache_key_idx  ON cell(cache_key);          -- cache-hit + negative-cache lookup
CREATE INDEX cell_version_idx    ON cell(version);            -- reconcile-fetch (§4 step7)

-- =====================================================================
-- DOCUMENT + CHUNK (§7 doc modes, §9 citations, §11 external gate)
-- =====================================================================
CREATE TABLE document (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id        uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  row_id         uuid REFERENCES "row"(id) ON DELETE CASCADE, -- package docs live under their row (§6)
  url            text,
  doc_type       text,
  format         text,
  storage_key    text,                                   -- Cloudflare R2 (§15)
  has_text_layer boolean,
  ocr_status     text,                                   -- null|pending|ok|failed (§7)
  source_lang    text,                                   -- citations stay in source language (§9)
  external_ok    boolean NOT NULL DEFAULT false,         -- §11 HARD GATE: connector=true, upload=false until attested
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX document_row_idx ON document(row_id);

CREATE TABLE chunk (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id    uuid NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  ordinal        integer NOT NULL,
  text           text NOT NULL,
  page           integer,
  char_start     integer,
  char_end       integer,
  embedding      vector(1024),        -- dim PINNED to embed_model_id (bge-m3 / multilingual UA-RU-EN); §10
  embed_model_id text NOT NULL,       -- §10: retrieval compares only same-model vectors
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chunk_document_idx ON chunk(document_id);
-- ANN index added week 2 once embed model + dim are final:
--   CREATE INDEX ON chunk USING hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- CROSS_ROW_RESULT (§8, §16 #6 — outside the column DAG, preserves isolation)
-- =====================================================================
CREATE TABLE cross_row_result (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id              uuid NOT NULL REFERENCES "case"(id) ON DELETE CASCADE,
  recipe_id            uuid NOT NULL,
  recipe_version       integer NOT NULL,
  row_ids              uuid[] NOT NULL,               -- explicit user-declared input set (§8)
  column_ids           uuid[] NOT NULL,
  signal               jsonb NOT NULL,                -- typed status + payload
  evidence_jsonb       jsonb NOT NULL DEFAULT '[]',   -- shared attr + BOTH source records (§8, no naked assertion)
  input_versions_jsonb jsonb NOT NULL DEFAULT '{}',   -- for is_stale (never-auto-rerun, §4)
  is_stale             boolean NOT NULL DEFAULT false,
  run_id               uuid REFERENCES run(id),
  created_at           timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (recipe_id, recipe_version) REFERENCES recipe(id, version)
);
CREATE INDEX cross_row_case_idx ON cross_row_result(case_id);

-- =====================================================================
-- CELL_FEEDBACK (§12 eval — Oksana + named backup judge)
-- =====================================================================
CREATE TABLE cell_feedback (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  row_id        uuid NOT NULL,
  column_id     uuid NOT NULL,
  verdict       text NOT NULL,     -- correct | partial | incorrect | cannot_judge
  relevance     smallint,          -- 0..3
  error_type    text,              -- wrong_entity|missed_evidence|unsupported_claim|wrong_classification|citation_mismatch|incomplete|source_problem|other
  correct_value jsonb,
  judge_id      uuid,
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (row_id, column_id) REFERENCES cell(row_id, column_id) ON DELETE CASCADE
);
CREATE INDEX cell_feedback_cell_idx ON cell_feedback(row_id, column_id);
