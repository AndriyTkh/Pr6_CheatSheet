# CheatSheet — Access & Dependency Register

**Owner:** Maryna (product owner). Engineers update rows they own; Maryna approves closures.
**Status:** seeded 23.07.2026. `TBD` = fill at daily.
**Rule 1 — no secrets in this file.** Keys/tokens live in server env only. This file records *that* a secret exists, *where* it lives, and *who* owns it — never the value.
**Rule 2 — closure needs proof.** A row moves to ✅ only with evidence: a successful request log, a quota screenshot, a test export. "Seems to work" = ⏳.
**Rule 3 — resources only.** People, availability, meetings → `TASKS.md`, not here.

Status legend: ✅ verified with proof · ⏳ exists / not verified · ❌ missing / not chosen · 🔴 blocker for a week gate

---

## 1. External data sources & APIs

| Resource | Link | Owner | Who has access | Access path | Status | Verify before closing | Limits / quota | Provided by | Fallback | Handover to Babel |
|---|---|---|---|---|---|---|---|---|---|---|
| Prozorro API | https://prozorro.gov.ua/api (confirm exact endpoint) | TBD (data stream) | whole team (public) | direct, no key | ⏳ 🔴 wk1 | rate limits; **stable participant-search path** (official API/feed vs search index — page scraping ≠ connector) | TBD | free | cached dump / fixtures | n/a (public) |
| YouControl API (YouScore) | https://api.youscore.com.ua/swagger/index.html#/ | Maryna (key holder) | server only, via proxy | key in server env, single server-side proxy, request logging w/o secret | ⏳ 🔴 wk1 | API contract & fields vs pilot needs; **person→companies endpoint** (>1 day to verify → column goes to stretch) | **300 requests until end of summer**, extendable on request | Maryna | negative-cache + cached fixtures; manual lookup | re-issue key to Babel account |
| Web search provider (for Web Search recipe) | TBD — choose: Brave / Serper / Tavily / Google CSE | TBD | server only | key in server env | ❌ 🔴 wk2 gate | pricing, rate limits, ToS allows this use | TBD | TBD | none — P0 recipe, must exist | re-issue |
| OCR (uk/ru/en printed scans) | TBD — decide: local Tesseract vs cloud (e.g. Vision) | TBD | — | local lib **or** key in server env | ❌ | if local: traineddata quality on real scans; if cloud: key + billing + data policy | TBD | TBD | manual upload of txt | n/a or re-issue |
| LLM access via OpenRouter | https://openrouter.ai | TBD (account holder) | server only | key in server env | ⏳ | pinned model IDs (no auto/latest), provider allowlist, ZDR endpoints where available, fallback OFF, **cost cap set**, actual-model logging | cost cap: TBD $ | TBD | second pinned model, pre-validated only | transfer account or re-issue |

## 2. Infrastructure

| Resource | Link | Owner | Who has access | Access path | Status | Verify before closing | Provided by | Handover to Babel |
|---|---|---|---|---|---|---|---|---|
| GitHub repo | https://github.com/AndriyTkh/Pr6_CheatSheet | Andriy | team + Babel (access already granted) | GitHub accounts | ⏳ | all 5 have write; branch rules per CLAUDE.md | free | done — Babel already has access |
| Hosting (backend + frontend) | TBD | TBD | TBD | TBD | ❌ | deploy access list; recovery/restart procedure | TBD | transfer or redeploy |
| Database (Postgres) | TBD | TBD | TBD | server env connection string | ❌ | backups exist; who can restore | TBD | dump + restore |
| Secrets storage | server env on hosting | TBD | server admins only | — | ❌ | no secrets in client bundle or repo (grep check); who can rotate | — | rotate all keys at handover |
| Google Cloud project `cheatsheet-pilot` (export creds, storage, sandbox) | TBD (project link after creation) | Maryna (project Owner) | team = project-level Editor, no org access | creds in server env; team members via own Google accounts | ❌ | org policy allows external members (test with 1 account); budget + alerts set; test export from the app passes; **any Vertex/LLM use on the critical path = same rules as OpenRouter (pinned, eval, logged)** | Maryna (Babel billing, budget-capped) | seamless — already under Babel account |

## 3. Team tools

| Resource | Link | Owner | Who has access | Status | Notes |
|---|---|---|---|---|---|
| Trello board | TBD (link) | Andriy | whole team | ⏳ | status tokens sync w/ TASKS.md per CLAUDE.md |
| Claude Team | https://claude.ai | KSE (provided) | whole team | ⏳ | confirm seats & who is admin |

---

## Open questions for the team (fill at daily, then delete)

1. Web search provider — which one, whose key, what budget? (blocks week-2 gate)
2. Hosting + DB — where do we deploy, who has access?
3. OCR — local Tesseract or cloud? Decision + owner.
4. OpenRouter — whose account, cost cap number, who reviews spend weekly?
5. Prozorro — which exact path for participant search is the "stable" one?
6. YouControl — licensed modules & fields check, person→companies endpoint (deadline: if >1 day → stretch).
7. GCP `cheatsheet-pilot` — Maryna creates wk1–2: check org policy (external accounts), set budget + alerts, add team as Editors.
8. Anything else? Each stream owner names accesses / resources they will need that are not yet in this register.

## Changelog

- 23.07 — seeded by Maryna.
