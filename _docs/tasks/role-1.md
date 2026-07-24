# Role 1 — Coordinator: legal, data & stakeholder liaison

> Part of `_docs/TASKS.md` (index: gates, people, tracking rules, cross-role notes). Read the index once, then work only in this file. Edit only the `Status` line of a task you own.

Mandate: you don't write product code. You keep the other four unblocked — real files, real access, real feedback, and you're the one who checks nothing in the pipeline breaks the "public data only" rule or leaves a secret somewhere it shouldn't be. Primary references: owner-brief §10–§12, §15; ARCHITECTURE.md §11.

**Verify note:** this role's deliverables are documents and human sessions, not code — tasks here carry no runnable `Verify` line. "Done" = the named artifact exists and the person who depends on it has confirmed receipt.

### Week 1 (2026-07-22 – 2026-07-28)

- **Task: Run kickoff decisions to closure**
  - **Status:** `DONE` @marina
  - **Target date:** `2026-07-22`
  - Description: Drive the 7 decisions owner-brief §12 requires before the team splits up: who owns which stream, when Oksana picks company X and is available for the first workflow session, what the row v0 unit is (ARCHITECTURE.md now **locks** it — "one Prozorro tender *lot*", §16 #3, rev. 3's change from the earlier tender-package grain — get it confirmed against real data, not just accepted on paper), which P0 recipe ships first (ARCHITECTURE.md §6 now flags **Structured Extract** as the pilot-priority candidate — confirm or override), where the backlog lives and who makes product calls, what access/keys/quotas already exist vs. are missing, and what one-lot-row end-to-end result the team commits to showing at the end of week 1.
  - Inputs: owner-brief §12, the team itself.
  - Deliverable: a short written decision log (backlog location is fine) covering all 7 points.
  - Depends on: nothing — this is the first task of the project.
  - Reference: [owner-brief §12]; §16 #3, §6.

- **Task: Build the access/dependency register**
  - **Status:** `WIP` @marina
  - **Target date:** `2026-07-23`
  - Description: One document listing every external dependency the pilot touches: Prozorro API (public, no auth), YouControl API key + which licensed modules it actually covers (registry vs. metered add-ons — "having a key ≠ having all modules," §6a), OpenRouter key, Cloudflare R2 bucket/credentials, Railway project access, Google account(s) for Sheets/Docs export. For each: who holds it, where it's stored (never in the repo or client), what's still missing.
  - Inputs: whatever keys the team already has (owner-brief §10 notes YouControl's key already exists).
  - Deliverable: `dependency register` doc, kept current through the build weeks and the buffer.
  - Depends on: nothing to start; backend dev needs this register's contents (specifically the YouControl key) within the first two days.
  - Reference: §6a, §11; [owner-brief §10, §12.6, §15 "API й ключі"].

- **Task: Hand off secrets server-side only**
  - **Status:** `DONE` @marina
  - **Target date:** `2026-07-24`
  - Description: Get the YouControl key (and any other provider keys) to the backend developer through a private channel, never committed or pasted into shared docs/chat history that persists in the repo. Confirm with backend dev that the key lands behind one server-side proxy endpoint, not in frontend code or logs.
  - Inputs: keys from the dependency register.
  - Deliverable: confirmation the backend dev has what they need and it's not in git.
  - Depends on: dependency register task above; backend dev's connector work (Role 2, same week).
  - Reference: §11 "Secrets server-side only."

- **Task: Draft legal/compliance guardrails**
  - **Status:** `WIP` @marina
  - **Target date:** `2026-07-23`
  - Description: Write the operating rules for what counts as "public data" for this pilot, what "external_ok" attestation means in practice for a manually-uploaded file (§11), and what Ukrainian personal-data-handling considerations apply to company officer/beneficiary data pulled from YouControl (names, addresses, EDRPOU) even though the source registry itself is public. This is the checklist backend/DS devs test against, not a legal memo nobody reads.
  - Inputs: ARCHITECTURE.md §11 (external_ok gate), owner-brief §10 ("Дані").
  - Deliverable: a short guardrails doc + a plain-language checklist for "can this document/field go to an external LLM/API provider?"
  - Depends on: nothing.
  - Reference: §11; [owner-brief §10].

- **Task: Run Oksana's first workflow session**
  - **Status:** `DONE` @marina — notes: [Excalidraw workflow](https://link.excalidraw.com/l/5iKoSi2GiB4/91hpw3JuCS)
  - **Target date:** `2026-07-25`
  - Description: Schedule and sit in on Oksana walking through her *manual* process for the company-X case — this defines what a "logical row" needs to contain, what fields matter, and what failure states actually happen in practice (not just the ones in the doc). Capture it in writing/recording.
  - Inputs: Oksana's availability, company X chosen (may happen in this same session).
  - Deliverable: session notes handed to backend dev + DS/agentic pair — feeds row v0 confirmation and the first eval rubric.
  - Depends on: kickoff decisions task (company X pick).
  - Reference: [owner-brief §11, §5 canonical scenario].

- **Task: Draft the first eval rubric with Oksana**
  - **Status:** `TODO`
  - **Target date:** `2026-07-27`
  - Description: Get Oksana's verdict categories (correct/partial/incorrect/cannot judge), relevance scale (0–3), and error-type taxonomy turned into a written rubric the eval track can wire up from day one.
  - Inputs: owner-brief §8/§12 feedback-form spec.
  - Deliverable: rubric doc, shared with DS/agentic pair (they wire `cell_feedback` capture to it).
  - Depends on: Oksana's first session.
  - Reference: §12; [owner-brief §8].

### Week 2 (2026-07-29 – 2026-08-04) — merges the original plan's weeks 2+3

- **Task: Curate real input files for extraction/OCR testing**
  - **Status:** `TODO`
  - **Target date:** `2026-07-29`
  - Description: Collect a batch of real tender documents (scanned PDFs included) that are legitimately public, covering the messy cases (no text layer, mixed language) the DS/document track needs to test docling/OCR against. Validate each file's public-source status against the Week 1 guardrails before handing it over.
  - Inputs: guardrails checklist; Prozorro document links.
  - Deliverable: a vetted sample file set + a short note on source/provenance for each.
  - Depends on: legal guardrails task; Prozorro connector live (Role 2/3-4) to pull real doc links.
  - Reference: §7, §11; [owner-brief §4 P0 "базовий OCR"].

- **Task: Run Oksana's vertical-slice review**
  - **Status:** `TODO`
  - **Target date:** `2026-07-31`
  - Description: After this week's connector volume ramp-up, get Oksana to look at real rows and give first-pass feedback (not formal eval yet — sanity check).
  - Inputs: rows in the grid (Role 2/5 output).
  - Deliverable: feedback notes routed to whichever track they concern.
  - Depends on: Week 2 gate progress (Web Search producing a verifiable column).
  - Reference: [owner-brief §11].

- **Task: Curate dev/held-out examples per recipe**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: Work with Oksana to pick which real examples go into the tuning set vs. the frozen held-out set for each P0 recipe (Summarize, Classify/Score added this week). Held-out means held-out — no peeking to tune after it's frozen.
  - Inputs: recipe outputs so far; eval rubric.
  - Deliverable: labeled dev/held-out split, one per recipe, documented so nobody accidentally tunes on held-out.
  - Depends on: eval rubric (week 1); recipes live (Role 3-4).
  - Reference: §12; [owner-brief §8, §11].

- **Task: Keep the dependency register current**
  - **Status:** `TODO`
  - **Target date:** `2026-08-01`
  - Description: Add any new keys/quotas requested this week (embedding model, additional OpenRouter models, R2 bucket details).
  - Inputs: requests from backend/DS devs.
  - Deliverable: updated register.
  - Depends on: ongoing.
  - Reference: §11.

- **Task: Run Oksana's 2-column-sequence session (week 2 gate)**
  - **Status:** `TODO`
  - **Target date:** `2026-08-04`
  - Description: Sit Oksana down to build a ≥2-column recipe sequence herself — this *is* half of the week 2 gate (the other half is Web Search stabilizing), not just feedback. Capture friction points for frontend/recipe tracks.
  - Inputs: recipe builder UI (Role 5), ≥2 working recipes (Role 3-4).
  - Deliverable: gate confirmation + friction-point notes.
  - Depends on: frontend recipe builder, DS/agentic recipes reaching "usable" state.
  - Reference: [owner-brief §11]; §14 week 2 gate.

### Week 3 (2026-08-05 – 2026-08-11)

- **Task: Curate journalist workflow / pattern examples**
  - **Status:** `TODO`
  - **Target date:** `2026-08-05`
  - Description: Turn owner-brief §3's pattern list (repeated participant groups, price anomalies, timing red flags, shared addresses/directors, etc.) into concrete annotated examples from the real dataset — this is what the DS/agentic pair tunes Classify/Score and Cross-row connect/Pair builder against, and what Oksana's feedback pass (below) references.
  - Inputs: real row data (by now there should be hundreds); Oksana's domain knowledge.
  - Deliverable: annotated pattern-example doc.
  - Depends on: connector volume ramp-up (Role 2/3-4).
  - Reference: [owner-brief §3 "Що система може показати"].

- **Task: Coordinate Oksana's tuning feedback pass**
  - **Status:** `TODO`
  - **Target date:** `2026-08-08`
  - Description: Get Oksana's marks on the cross-row signals, the new Companies/Pairs sheets, and classification outputs so the DS/agentic pair can tune recipes this week.
  - Inputs: cross-row connect output, Pair builder output, Classify/Score output.
  - Deliverable: feedback logged in `cell_feedback` via the UI (Role 5) or relayed directly to Role 3-4.
  - Depends on: cross-row connect + Pair builder + classify/score working.
  - Reference: [owner-brief §11].

### Week 4 (2026-08-12 – 2026-08-18) — merges the original plan's weeks 5+6, ends on Demo Day

- **Task: Freeze the held-out set**
  - **Status:** `TODO`
  - **Target date:** `2026-08-12`
  - Description: Lock the held-out examples with Oksana — no further tuning against them from this point. Confirm the dev track has actually stopped touching them.
  - Inputs: held-out set from week 3 curation.
  - Deliverable: written confirmation of freeze date + scope.
  - Depends on: dev/held-out task (week 2).
  - Reference: §12; [owner-brief §8, §11].

- **Task: Legal/security audit pass**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Verify (with backend dev) that no non-public material entered the pipeline, `external_ok` attestations are actually being checked and logged, and no secrets leaked into logs, the repo, or client-side code.
  - Inputs: guardrails checklist (week 1); backend dev's logging/proxy implementation.
  - Deliverable: audit sign-off or a punch list of fixes before Demo Day.
  - Depends on: backend security work (Role 2, §11 tasks).
  - Reference: §11; [owner-brief §11 "перевірка permissions, секретів"].

- **Task: Draft handover/IP documentation**
  - **Status:** `TODO`
  - **Target date:** `2026-08-13`
  - Description: Per owner-brief §15's "handover doesn't happen" risk — write down what transfers to Бабель: repo ownership, secrets/keys, hosting account, billing, domain, and who's the accepting owner on their side. Draft now, finalize once Demo Day results are in.
  - Inputs: dependency register; Railway/hosting account details from backend dev.
  - Deliverable: handover doc draft.
  - Depends on: dependency register being current.
  - Reference: [owner-brief §15 "Не відбудеться передача продукту"].

- **Task: Prep and coordinate the live demo run**
  - **Status:** `TODO`
  - **Target date:** `2026-08-17`
  - Description: Line up Oksana for the live run, prep a backup dataset/run in case of an external failure (API downtime, etc.) per the Demo Day gate.
  - Inputs: frozen held-out set; stable build (Role 2/5).
  - Deliverable: demo runbook + backup dataset ready.
  - Depends on: everything else landing this week.
  - Reference: §14 week 4 gate; [owner-brief §13 demo contract].

- **Task: Finalize handover + "what's next" decision doc**
  - **Status:** `TODO`
  - **Target date:** `2026-08-18`
  - Description: Close out the handover doc, and write up the Stop/Iterate/Operationalize/Expand recommendation per owner-brief §16. If Demo Day slips into the buffer (§14a), this task slips with it.
  - Inputs: handover draft; demo results.
  - Deliverable: final handover package + decision memo.
  - Depends on: Demo Day run.
  - Reference: [owner-brief §16].
