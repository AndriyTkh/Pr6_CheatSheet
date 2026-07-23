# CheatSheet — Investigation Workflow (Desired UX)

> **Archived source doc — still cited, not still authoritative.** Its content was folded into `_docs/ARCHITECTURE.md` during the rev. 3 workflow-integration pass, which is now the contract. Several `§` sections there still cite this file by section number (`desired-workflow.md §1`–`§7`) for the *scenario* behind a decision — follow those citations here, but where this file and ARCHITECTURE.md disagree, **ARCHITECTURE.md wins**.

From one journalist's question to cited tender columns, verified companies, and reusable relationship tables.

**Scenario used throughout:** Journalist's question: *Which 2026 tenders did KSE enter as a bidder, and which source-backed signals or patterns deserve review?*
Case setup: entity = KSE, role = bidder/supplier, period = 2026, public data only.

---

## Act 1 — Baseline demo

### 1. Get started

- **Journalist** asks the question or supplies source files.
- **Input A — question:** assistant normalizes the case, resolves "KSE" to a legal identifier, proposes Prozorro as source, waits for journalist approval, then runs.
- **Input B — own sources:** PDFs, OCR-ready scans, conversation transcripts, video transcripts/subtitles. (Raw video imagery is not analyzed in the pilot.)
- **System output:** `@tenders` (one row per tender lot) or `@documents` (one row per source document). Hidden chunks support retrieval and citations.
- → Read `@tenders`

### 2. Extract answers

- **System reads** `@tenders`: tender ID, lot ID, status, date, buyer, subject, bids, award, source URL.
- **Journalist** adds one declared question per new column:
  - Who won? → `@winner`
  - What was the amount? → `@amount`
  - Who else participated? → `@participants`
  - What did the buyer require? → `@requirements`
- **Output rule:** every answer links to the exact source record.
- **Pattern note:** canceled → relaunched is visible by sorting. Act 2 can automate this once matching rules exist.
- → Use `@winner` ID

### 3. Enrich with YouControl

- **Recipe reads** `@winner` using `identifier.scheme` + `identifier.id` (EDRPOU only when scheme is `UA-EDR`).
- **External source:** YouControl registry evidence.
- **New columns:** `@owner`, `@creation_date`, `@related_companies`, `@companies_at_address`, `@companies_owned_by_owner`.
- **Optional agent step:** with approval, use `@owner` as seed to create `@companies_owned_by_owner`. Every result retains its own citation.

> The same CheatSheet core works for other scenarios: source rows → one declared question per column → optional registry/web enrichment → scoring and classification → sorting → human review. YouControl, participant expansion, and pair analysis are optional modules used only when the journalist's question requires them.

- → Reuse `@winner`

**Preset — potential review signals**
- Baseline: newly created company; relevant negative coverage; amount anomaly against a defined benchmark.
- After expansion: owner or address link to another bidder.
- → Apply the preset

### 4. Search the open web

- **Recipe reads** `@winner` (canonical name) + an explicit time window.
- **Journalist's question:** What did public reporting say about this company during the previous 12 months?
- **System:** runs a row-isolated web search, keeps relevant results, records publication dates.
- **Output:** `@media_mentions` — relevant coverage, including potential negative mentions, with source links for every claim.
- → Use cited evidence

### 5. Score and classify

- **Scoring recipe** reads `@amount`, `@creation_date`, `@owner`, `@media_mentions`, applies the visible preset.
  - **Output:** `@review_priority` (0–10 + explanation). Prioritizes review; not a finding of wrongdoing or a collusion probability.
- **Classification recipe** reads requirements, evaluation criteria, all bid values, award rationale.
  - **Output:** `@winning_factor` — price / terms / unclear / insufficient data — plus explanation.
- After Block 8, scoring can rerun with pair signals.

### 6. Sort, verify, and label

- **Journalist** sorts `@review_priority` highest to lowest, opens any cell, checks the exact cited source.
- **Human labels:** Correct / Error / Needs review.
- **System output:** labels and current progress are saved — become evaluation feedback for improving the recipe, restorable in the next session.
- **Result:** a persistent, reviewed working table — not an automated verdict.

---

## Act 2 — After the baseline demo

Continue with priority rows + evidence.

### 7. Expand participants

- **Deterministic recipe reads** the participant list stored in `@participants`.
- **System:** explodes the list, normalizes legal identifiers, deduplicates companies while preserving every company-to-lot link and source citation.
- **Output — Companies sheet:** one row = one canonical company; each row retains the tender lots it appeared in.
- **Next:** run the same YouControl, web search, scoring, classification, and custom recipes per company.
- → Expand `@participants`

### 8. Build a company-pair sheet

- **Deterministic pair builder reads** companies + preserved company-to-lot links.
- **System:** builds unique unordered pairs within each lot, aggregates the same pair across all selected lots.
- **Output — Pairs sheet:** one row = one company pair. Columns: `@shared_lots`, `@wins_A`, `@wins_B`, `@shared_owner_or_address`, `@evidence`.
- **Journalist can answer:**
  - Which competitors repeatedly appear together?
  - Which source-backed links deserve follow-up?
  - Which tenders were cancelled and relaunched with the same winner?
- A recurring pair is a lead, not proof of coordination.
- → Compare across lots
