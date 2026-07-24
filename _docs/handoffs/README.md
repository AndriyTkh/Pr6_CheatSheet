# Handoff notes

One file per branch: `_docs/handoffs/<branch-slug>.md` (e.g. `role-2-wk1-models-recipe-dag.md` — slashes become dashes).

**What this is for:** the context that dies when a session ends. Why an approach was abandoned, which rabbit hole was already explored, what's half-finished and where the seam is, what surprised you about the spec. The next session — yours, a teammate's, or a coding agent's — reads one short file instead of re-deriving it from a diff.

**What this is NOT:**
- Not status. Status lives on the `Status` line in `_docs/tasks/role-*.md`, one source of truth (root `CLAUDE.md §3`).
- Not a spec. If it's a rule the whole team must follow, it belongs in `ARCHITECTURE.md` or a `CLAUDE.md`, not here.
- Not a changelog. Git already has that. Write what git *can't* show: intent, dead ends, doubts.

## Rules

- **Append, don't rewrite.** Newest entry at the top, dated. History is the value.
- **Write it when you stop, not when you remember.** End of a session, end of a work block, before a context compaction. An agent working in this repo appends before finishing a task.
- **Short.** 5–15 lines. If it's longer than the diff, you're narrating instead of handing off.
- **Delete the file when the branch merges** — its content either landed in the code, in a doc, or didn't matter. Stale handoffs are worse than none.
- **No secrets.** Same rule as everywhere (§11): no keys, no tokens, no pasted credentials.

## Template

```markdown
# <branch> — handoff

## 2026-07-23 @who (or: agent session)
- **Landed:** what's actually done and verified (name the Verify command that passed).
- **In flight:** what's half-done, and exactly where the seam is (file:line).
- **Dead ends:** what was tried and abandoned, and why — this is the part that saves the next session an hour.
- **Spec friction:** anything in ARCHITECTURE.md that was ambiguous or wrong. Flag it, don't silently diverge.
- **Next:** the single next action, concretely.
```
