## Then if i understand the whole setup correctly we'd need such components

1. Database that serves all the table interractions
> Resolved: one central place holds everything - rows, columns, recipes, results, documents, feedback. No separate systems scattered around, so history/lineage never gets disconnected.

2. General format for cells/relations/recipe
> Resolved: a recipe takes some input columns and produces some output columns (can be several in, several out), and can be either plain deterministic logic or an AI agent - same shape either way. Every recipe is versioned, so old results always stay linked to the exact version that produced them, and don't silently change later.

3. A way to run those cells/recipes (lets replace the word with tasks)
> Resolved: simplest possible queue that grabs pending cells one at a time and works on them - no heavy extra system needed at our pilot's scale. Can swap in something beefier later if usage grows a lot.

4. UI
> Resolved: spreadsheet-style grid. Cells fill in live in the background as tasks finish, so you watch answers appear instead of waiting for one big batch.

5. ============ Different task groups (the recipe catalog)
>This initial group of tasks/instructions only includes tasks that are performed in one pass, taking one/several cells as input and giving one/several cells as output.
>For example: Take 1st and 2nd columns (company/owner), perform a websearch about when such owner took his place, and fill 3rd column as corresponding output.
>Resolved into a concrete starting set:

- WebSearch (agent digs up context from the open web)
- External registry/tender lookups (pulls official structured data straight in, no AI needed for the clean parts)
- Manual upload (user's own files; reads scanned pages too if needed)
- Structured Extract (pulls specific fields out into proper columns)
- Summarize (short summary of a text column)
- Classify / Score (labels or scores a row)
- Match & Verify (agent checks "is this really the same company/person" and shows its evidence)
- Cross-row connect (surfaces hidden links between rows - see below)
- Custom Prompt (stretch goal - free-form ask on a column)

> Also resolved: every cell result carries a clear status, not just blank/empty - e.g. "not found" vs "found conflicting info" vs "needs human review" vs "rejected, doesn't qualify". So it's always clear *why* a cell has no answer, not just that it doesn't.
> Also resolved: every value shows exactly where it came from - a link back to the source document/page/field, never a naked claim.
> Also resolved: if something upstream changes, dependent cells get flagged "outdated" but are never silently re-run - the user decides when to refresh, so nothing changes behind their back.

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

# Document processing

Resolved into three separate jobs, not one blob:

> Enumerate
Find *every* mention of something across a document, not just the top few matches - important when missing even one instance is a real failure.

> Structured Extract
Pull specific fields into clean structured data. Cheap and automatic for documents that are already official/structured (registry data); AI only gets involved for messy unstructured text.

> Ask-the-document / Q&A
"What does this document say about Y" - useful, but pushed out of the pilot for now to keep scope tight.

# Agentic connection research

Resolved as a bounded, two-step process (not "let an agent roam free"):

1. Find candidate pairs cheaply, using shared plain facts (same phone/address/owner/etc) - no AI needed for this narrowing step.
2. For each candidate pair, an agent double-checks by digging up real evidence and produces a confirmed connection with sources attached, not a guess.

> Marking two rows as duplicates of each other (Merge) works the same way, but actually changes what happens to a row afterward - held back until the plain connection-finding above is proven solid, though the groundwork for it is already built in.

# Trust / access

- Each case (project) is private by default - shared with others only by explicit invite from the owner.
- Pilot only ever touches public data.
- No full auto-pilot that plans and runs the whole investigation by itself for now - a human always picks which step runs on which rows. Letting the system plan/act on its own is a later step, once the core is proven trustworthy.

# How we'll know it's working

- Each recipe gets checked against a small real sample; part of that sample is kept hidden away for one final honest test at the end, so we're not just tuning to what we already tested.
- Human feedback per cell (correct / partial / wrong / can't judge) feeds back into improving the recipes.
