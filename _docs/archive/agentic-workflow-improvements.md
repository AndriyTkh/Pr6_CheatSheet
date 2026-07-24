# Agentic-workflow improvements — considered, not adopted

Companion to the workflow that *is* in force (`CLAUDE.md` §3–§7). This file is the other half: ideas that were evaluated during the rev. 3 workflow pass and deliberately **not** adopted, each with what it is, why it was deferred, and the trigger that should make us revisit.

**Read this before proposing a workflow change.** If your idea is here, the question isn't "is it good?" — several of these are good — it's "has its trigger fired?" If it has, say so and re-open it. If it hasn't, don't spend the team's attention re-deriving the same conclusion.

**What *was* adopted in the same pass**, for contrast: the per-role task split (`_docs/tasks/role-<N>.md`), a `Verify` line on every code task, `_docs/architecture-index.md` for section-range reads, `backend/CLAUDE.md` + `frontend/CLAUDE.md`, `_docs/handoffs/`, and `.claude/settings.json` + `.claude/hooks/verify-backend.sh`. The common thread: each of those either *removes* context cost or makes a claim mechanically checkable, and none of them can block a session when they misfire.

---

## A4 — Package repeatable procedures as `.claude/skills/`

**What it is.** Turn the recurring procedures now written as prose in `CLAUDE.md` into invocable skills: `add-recipe` (scaffold against the `recipes/base.py` contract + register the slug/version), `add-migration` (new numbered file, never an in-place edit, ORM mirror follow-up), `task-status` (flip one `Status` line, correct token, correct file), `open-pr` (Verify passed → handoff note → `REVIEW` → PR).

**Why deferred.** Prose in `CLAUDE.md` is loaded every session at zero marginal cost and is readable by the humans on the team, who outnumber the agents. A skill is only worth its maintenance when the procedure has enough steps and enough repetitions that an agent reliably drifts from the prose — and we have four weeks and no repetition history yet. Extracting them now also risks the classic split-brain: the skill says one thing, `CLAUDE.md` §4/§5 still says another, and nobody knows which is canonical.

**Revisit when.** Any of: (a) a procedure is executed more than ~5 times and an agent gets it wrong at least twice; (b) `add-recipe` grows past ~4 steps once the Expand/Pair builders land in week 3; (c) `CLAUDE.md` crosses the length where sessions start skimming it. First candidate is `add-recipe` — highest repetition, most contract surface (§3, §6).

---

## B1 — `PreToolUse` deny hook on migrations and shipped recipe versions

**What it is.** A hook that hard-blocks `Edit`/`Write` against `_docs/migrations/*.sql` and any shipped `recipe_version`, making `CLAUDE.md` §5's "the schema is locked" mechanical rather than honor-system. Today the lock is a sentence in a doc; a hook would make an in-place migration edit *impossible* rather than merely *against the rules*.

**Why deferred.** Only because a deny hook can block legitimate work. The backend/DB owner is *supposed* to add migration `0003`, and a path-glob deny can't distinguish "adding a new numbered file" (fine) from "editing `0001` in place" (forbidden) without more nuance than a first-cut hook carries — and a hook that blocks the owner from doing their own job gets disabled wholesale, taking the protection with it. The honor-system version has held so far: no one has edited a migration in place.

**Revisit when.** Anyone actually edits a migration in place, or a shipped `recipe_version`, even once. That single event flips the cost-benefit — write the hook then, scoped to *modification of existing numbered files* rather than to the whole directory, so creating `0003` stays unblocked. A near-miss caught in review counts as the trigger; don't wait for one to merge.

---

## C2 — Plan-mode gate before code on contract-touching tasks

**What it is.** For any task that touches an `ARCHITECTURE.md` contract (schema mirroring, the `recipes/base.py` shapes, DAG readiness, the `citation_jsonb` array shape), require the agent to produce and get approval on a plan before writing code.

**Why deferred.** `Verify` already carries most of this weight from the other end: a task can't claim `REVIEW` without a passing command, so a contract misreading surfaces as a failing test rather than as merged drift. Adding a mandatory approval round-trip to every contract task costs a human turn per task in a 4-week schedule where the coordinator is also the legal/data liaison. The gate would be paying for itself only on the tasks where the spec is genuinely ambiguous — and `CLAUDE.md` §4 step 6 already says to flag those instead of diverging silently.

**Revisit when.** A contract-touching task ships something that passed its `Verify` but violated the spec anyway — i.e. the failure mode `Verify` can't catch. Also worth it if the `citation_jsonb` shape between Role 3/4 and Role 5 turns into a real mismatch: that cross-role seam is the one place a plan-first round-trip is clearly cheaper than the rework.

---

## C3 — One git worktree per agent

**What it is.** Give each concurrent agent its own `git worktree` instead of sharing one checkout, so parallel agents can't collide over branch switches and file writes.

**Why deferred.** Not deferred on merit — it's the right answer for real parallelism, and `CLAUDE.md` §4a already names it ("One agent per checkout... if you need real parallelism, use a git worktree per agent"). What's deferred is *mandating* it: worktrees multiply the environment setup (a venv, a `.env`, a `node_modules` per tree) on a team where not everyone runs agents, and most sessions are single-agent, where the convention costs setup and buys nothing.

**Live example, not hypothetical.** A concurrent agent working `backend/` in this very checkout is exactly the collision this prevents — it's why this session was constrained to "don't switch branches, don't touch `backend/`". That constraint is the manual version of the isolation a worktree would give for free.

**Revisit when.** Two agents need to run concurrently on overlapping trees more than once, or the "don't switch branches under the other agent" rule gets violated and costs real rework. At that point write the setup down (worktree per `role-<N>/<slug>`, shared Postgres, per-tree venv) rather than re-deriving it under pressure.

---

## C4 — Reviewer subagent on your own diff pre-PR

**What it is.** Before opening a PR, run a reviewer subagent over your own diff — looking specifically for schema-mirror drift (`models/` ahead of `0001`/`0002`), missing `§N` citations, and `Verify` lines that don't actually exercise the deliverable.

**Why deferred.** Half-adopted, not rejected: `CLAUDE.md` §4a *recommends* it ("delegate diff review before a PR"). What's deferred is making it a required step in §4's numbered workflow. A reviewer pass on a 30-line task-sized diff often costs more than the human review it precedes, and mandatory self-review tends to decay into a rubber stamp — the agent that wrote the drift is not reliably the one that spots it. Recommended-and-used beats required-and-ignored.

**Revisit when.** Schema-mirror drift or a missing citation reaches `master` more than once, or PRs start arriving big enough (>~200 lines) that a human reviewer's attention is the scarce resource. Then promote it from §4a advice to a numbered step between "Verify passes" and "open a PR".

---

## C5 — Trello sync as a versioned skill

**What it is.** The board convention is currently tribal knowledge held by whoever last synced: board **"KSE No6"**, card name = the task title **verbatim** from `_docs/tasks/role-<N>.md`, due date = the task's `Target date`, list = the `Status` token via the `CLAUDE.md` §3 mapping. Promoting it to a `.claude/skills/` entry would make it shared and versioned instead of remembered.

**Why deferred.** Same reason as A4, plus one more: the board is a *mirror*, and `CLAUDE.md` §3 is explicit that the `Status` line is the single source of truth with "no second tracker to keep in sync". Automating the mirror makes it feel authoritative, and a skill that writes to Trello without reading back is one more place for the two to diverge silently. The convention is also small enough to state in four lines — which is what it's now doing here, so it is at least no longer purely tribal.

**Revisit when.** The board goes stale enough that someone reads a wrong status off it, or a second person starts syncing it (two people improvising the same convention is when it needs to be written down). If adopted, the skill must sync **`_docs/tasks/role-<N>.md` → Trello, one direction only** — never the reverse, or `CLAUDE.md` §3 stops being true.

---

## The bar for adopting any of these

Two questions, both from the pass that produced this file:

1. **Does it reduce context cost or make a claim mechanically checkable?** Anything else is ceremony, and ceremony is what a 4-week schedule can't afford.
2. **What does it do when it misfires?** Everything adopted so far degrades to silence — the verify hook is quiet without a venv, the architecture index is just a pointer. Everything deferred here can, when wrong, *block* a session (B1), *cost a turn* (C2, C4), or *lie* (C5). That asymmetry is the actual reason these are on this side of the line, and it's the first thing to re-check when a trigger fires.
