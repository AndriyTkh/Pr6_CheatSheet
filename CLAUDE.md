# CheatSheet — Start Here

**Read this file at the start of every session (human or coding agent) before touching anything.**
It is the map. It tells you which doc is the source of truth for what, how to record progress, and the git rules that keep 5 people + coding agents from colliding.

CheatSheet is a **columnar, lineage-tracked compute graph over rows** — a spreadsheet on the surface, a build-system/DAG engine underneath — built as a pilot over Prozorro + YouControl — 4-week build + 1.5-week buffer, `_docs/ARCHITECTURE.md §14` (see `_docs/ARCHITECTURE.md §0`).

---

## 1. Read order (every session)

| Order | File | Read it for |
|-------|------|-------------|
| 1 | **`CLAUDE.md`** (this file) | The map, tracking rules, git rules, delegation policy. |
| 2 | **`_docs/TASKS.md`** | The index: weekly gates, people, tracking + `Verify` rules. Read once; it's short by design. |
| 3 | **`_docs/tasks/role-<N>.md`** | **Your** task list. Find your task, check its `Status`, check its `Depends on` is `DONE`. Read only your own file. |
| 4 | **`_docs/architecture-index.md`** → **`_docs/ARCHITECTURE.md`** | **The technical contract.** All `§N` references point into ARCHITECTURE.md. Use the index to read the cited sections by line range — don't load all 568 lines. |
| 5 | **`<dir>/CLAUDE.md`** | Auto-loaded when you work in `backend/` or `frontend/` — run commands, local conventions, non-negotiables for that tree. |
| 6 | **`_docs/repo-structure.md`** | Where your code lands — the folder skeleton, mapped to `ARCHITECTURE.md` sections. |
| 7 | **`_docs/handoffs/<branch>.md`** | If one exists for your branch: what the last session learned, tried, and abandoned. Write one before you stop. |
| ref | **`_docs/tech-stack-decision.md`** | *Why* each tech pick (companion to ARCHITECTURE.md's *what*). Read when a choice surprises you. |
| ref | **`_docs/migrations/0001_core_schema.sql`** | **Locked schema contract.** Read-only for everyone except the backend/DB owner. Changed only via a new numbered migration + team agreement. |
| ref | **`_docs/archive/`** | Source briefs (owner brief, product vision, rough outline). Historical — `[owner-brief §N]` refs in the task files point into `cheatsheet-owner-brief.md`. |

---

## 2. Doc map — what each file owns

Each fact has exactly one home. Don't restate a spec in another doc; link to it.

- **`_docs/ARCHITECTURE.md`** — the *what* and the *how* of the system. Canonical `§N` anchors. Change only by team agreement; it is the contract every recipe and route is built against.
- **`_docs/architecture-index.md`** — a *pointer* into the above (section → line range). Never quote a spec from it; regenerate it in the same commit as any ARCHITECTURE.md edit.
- **`_docs/TASKS.md`** — the index: gates, people, tracking + `Verify` rules, cross-role dependencies. Rarely changes.
- **`_docs/tasks/role-<N>.md`** — the *who* and the *when*. One file per role, week-ordered, plus the live `Status` of each task. These are the docs that change daily.
- **`backend/CLAUDE.md`, `frontend/CLAUDE.md`** — per-tree conventions and run commands. Loaded only when you work there.
- **`_docs/handoffs/`** — session-to-session context (dead ends, seams, doubts). Not status, not spec. Deleted when the branch merges.
- **`_docs/repo-structure.md`** — the *where*. Folder layout. Update when you add a real folder the skeleton didn't predict.
- **`_docs/tech-stack-decision.md`** — the *why* behind stack picks.
- **`_docs/archive/desired-workflow.md`** — the pilot journalist workflow ARCHITECTURE.md was specced against. Archived, but several `§` sections still cite it by section number — follow those citations there.
- **`_docs/agentic-workflow-improvements.md`** — the workflow ideas considered but not adopted, with the reason. Read before proposing one again.
- **`_docs/migrations/0001_core_schema.sql`** — the *frozen data contract*. The ORM mirrors it, never the reverse.
- **`_docs/archive/`** — superseded docs and source briefs. Read-only history: nothing here describes live work, and nothing here is a status you should trust.

If you rename or move any doc, fix its inbound references in the same commit (grep the old name across `_docs/` and `CLAUDE.md`).

**Superseding a doc means moving it to `_docs/archive/`**, in the same commit, with a header saying what replaced it — not leaving it in `_docs/` to rot. Two files describing the same live work is the exact failure §3 exists to prevent: the copies drift, and the one you happen to open decides what you believe.

---

## 3. Progress tracking

Status lives **inline in `_docs/tasks/role-<N>.md`**, one `Status` line per task. That line is the single source of truth — there is no second tracker to keep in sync.

**Status tokens** (these map 1:1 to the Trello board columns):

| Token | Means | Trello column |
|-------|-------|---------------|
| `TODO` | not started | Backlog / This Week |
| `WIP` | in progress | In Progress |
| `BLOCKED` | waiting on a dependency or a decision | Blocked |
| `REVIEW` | done, in PR / awaiting handoff acceptance | Review/Handoff |
| `DONE` | merged + dependents unblocked | Done |

**How to update:** edit only the `  - **Status:** ...` line of the task you are on. Optionally append who + branch/PR:

```
  - **Status:** `WIP` @nazar role-2/schema-models
  - **Status:** `BLOCKED` waiting on Role 1 YouControl key
  - **Status:** `REVIEW` PR #14
  - **Status:** `DONE`
```

**`Verify` is what `DONE` costs.** Every code task carries a `Verify` line — the command (or named manual check) that proves the deliverable. Don't set `REVIEW` until it passes; if the test file it names doesn't exist yet, writing it is part of the task; a silently skipped test is not a pass. Full rules: `_docs/TASKS.md` "Verify".

**Weekly gates are the heartbeat.** The gate table in `TASKS.md` has a `Gate status` column (`PENDING` / `MET`), edited only by the coordinator. A week does not advance until its gate is `MET`. If you want one number for "how's the project doing," it's "which gates are `MET`."

**Blocked is a signal, not a dead end.** Set `BLOCKED` with the reason; the coordinator clears blockers (that column is theirs to watch).

---

## 4. Coding-agent workflow (per session)

1. Read `CLAUDE.md` → `_docs/TASKS.md` (index) → **your** `_docs/tasks/role-<N>.md`. Then the `§N` sections your task cites, via `_docs/architecture-index.md` line ranges. Don't read the whole ARCHITECTURE.md, and don't read other roles' task files.
2. Check `_docs/handoffs/<branch>.md` if one exists — it's the cheapest context you'll get.
3. Pick a `TODO` task whose `Depends on` tasks are all `DONE`. If nothing is unblocked, say so — don't start blocked work.
4. Create a branch: **`role-<N>/<short-slug>`** (e.g. `role-2/dag-cycle-check`). Never commit work to `master` directly. **If another agent or person is already working in this checkout, don't switch branches under them** — say so and work with what's checked out.
5. Set the task's `Status` to `WIP` on your branch.
6. Implement against the `§N` contract in `ARCHITECTURE.md`. If the spec is wrong or ambiguous, flag it — don't silently diverge; `ARCHITECTURE.md` is shared.
7. Run the task's `Verify` line. It passes, or the task isn't done.
8. Append a handoff note to `_docs/handoffs/<branch>.md` — dead ends, seams, spec friction. Do it before you stop, not from memory later.
9. Set `Status` to `REVIEW`, open a PR (one task ≈ one PR — small, reviewable).
10. On merge, set `Status` to `DONE` and delete the branch's handoff file. If your task was a handoff (a `Depends on` for someone else), tell that person their dependency is live.

### 4a. Delegation — what goes to a subagent

Context is the scarce resource in a long session. A subagent's file dumps stay in *its* context; only its conclusion comes back. So:

- **Delegate broad read-only search.** "Where is X defined", "what calls Y", "map this directory", "which recipes declare `per_item`" → an exploration subagent. You get the answer, not 40 file excerpts.
- **Delegate diff review before a PR.** A reviewer subagent on your own diff catches schema-mirror drift and missing citations before a human spends attention.
- **Do implementation in the main thread.** Editing code you've reasoned about is where continuity matters — handing it to a fresh agent means it re-derives the context you already paid for.
- **Never delegate a decision.** Spec ambiguity, scope, gate claims: those come back to the human. A subagent's conclusion is input, not authority — if it contradicts the contract, the contract wins.
- **One agent per checkout.** Parallel agents in the same working tree collide over branches and files. If you need real parallelism, use a git worktree per agent.

---

## 5. Git — avoid conflicts

The tracking design is built so parallel work doesn't fight. Keep it that way:

- **Branch per task/role:** `role-<N>/<slug>`. Merge via PR. Never push tracking edits straight to `master`.
- **One editor per `Status` line.** Different tasks are different, non-adjacent lines → git auto-merges them. You only ever edit the status of the task you own.
- **One file per role.** `_docs/tasks/role-<N>.md` — your daily edits and someone else's are in different files now, so they can't conflict at all. Don't edit another role's file; ask them.
- **Never reflow or reformat a doc you're not changing.** No editor "format on save" / rewrap on `ARCHITECTURE.md` or the task files — turning a 1-line change into a whole-file diff is what manufactures conflicts. `.editorconfig` disables trailing-whitespace churn for markdown; leave it on.
- **`.gitattributes` pins `eol=lf`.** On Windows, do not let your editor re-save these files as CRLF — that alone can conflict every line. The config handles it; don't override.
- **Small PRs, merge often.** A task-sized PR merged daily rarely conflicts. A week-long mega-branch always does.
- **The schema is locked.** `0001_core_schema.sql` changes only via a *new* numbered migration + team agreement — never an in-place edit. Same for any shipped `recipe_version`.

---

## 6. Guardrails always in force (ARCHITECTURE.md §11)

- **Public data only.** Every document carries `external_ok`; un-attested sources are blocked from external providers, never silently sent.
- **Secrets server-side only.** Provider keys live behind one server proxy — never in the repo, client, or logs.
- **Isolation is structural.** A recipe never reaches outside the `row_context` the framework hands it.

---

## 7. Harness config (`.claude/`)

Checked in, team-shared — treat it like any other repo config.

- **`.claude/settings.json`** — a permission allowlist (read-only git, `pytest`, `ruff`, `npm run build`, migrations, `docker compose ps/logs`) so routine verification doesn't stop for a prompt, plus the verify hook below. Allowlist only — nothing is denied here, so no workflow is blocked by it. Add an entry when a command proves both routine and safe; never add a mutating one.
- **`.claude/hooks/verify-backend.sh`** — runs after every `Edit`/`Write`. If the edited file is a `.py` under `backend/`, it runs `ruff check --fix` on it and the backend suite; failures come straight back to the agent so it fixes its own edit in-loop. Silent for every other file, and silent on a machine without the toolchain — it never blocks the session for a missing venv.

If a hook misfires, fix the hook and say so. Don't route around it.
