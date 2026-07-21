# Tech Stack — Decision Record

**Status:** decided for pilot · companion to `ARCHITECTURE.md` (this doc explains *why*, the plan states *what*)

---

## 0. Constraints that shaped the picks

- Team (3-4 devs) is currently on a **Python course** → weights backend/worker language toward Python, especially since the hardest work (agentic recipes, embeddings, OCR) leans on Python's AI ecosystem.
- Browser frontend needs JS/TS regardless of backend language — no way around this for a custom virtualized grid UI.
- 6-week pilot, small team → prefer low-ops, well-trodden libraries over building plumbing from scratch (job queue, auth) or heavy frameworks with more ceremony than payoff (Next.js SSR, Prisma migrations vs raw CTEs).
- Production version is expected to eventually support **web + local-PC** (mobile less likely) with a **private mode** that blocks external API calls on private-data cases — see §3 Unresolved.

---

## 1. Final stack

| Layer | Pick | Alternatives considered |
|---|---|---|
| Database | **Postgres** (+ `pgvector`, `jsonb`) | — (fixed in main plan §1; one source of truth for DAG/cells/chunks/eval, no second DB) |
| Backend language | **Python** | TypeScript (Node) |
| Backend framework | **FastAPI** | Fastify (Node), Express, Django |
| Frontend | **React + TypeScript, Vite** | Next.js, SvelteKit |
| Grid UI | **TanStack Table + virtual scroll** | — (fixed in main plan §1; headless, React-first, handles 100s of live-filling rows) |
| DB access | **SQLAlchemy 2.0 (async) + raw SQL for CTEs** | Prisma, Drizzle, plain `asyncpg` only |
| Job queue | **Procrastinate** | pg-boss/BullMQ+Redis, hand-rolled `SKIP LOCKED` poller |
| Realtime transport | **SSE** (`sse-starlette`) | WebSocket, polling |
| LLM access | **openai python SDK → OpenRouter base_url** | Vercel AI SDK, litellm, provider-native SDKs |
| OCR | **pytesseract** (Tesseract engine) | Cloud Document AI / Textract / Azure OCR |
| File storage | **Cloudflare R2** | AWS S3, Supabase Storage, local disk |
| Auth | **fastapi-users** | Better-Auth (TS-only, ruled out with backend switch), Clerk, Auth.js |
| Hosting | **Railway** | Render, Fly.io, self-hosted VPS |
| Desktop wrap (future) | **Tauri** | Electron |
| Mobile | deferred | — |

---

## 2. Rationale by layer

### Database — Postgres
Already fixed in the main plan. One database for DAG, cells, chunks, provenance, and eval avoids the operational cost of a second store (e.g. a separate vector DB) for a pilot at this scale. `pgvector` covers embeddings; `jsonb` covers flexible per-recipe schemas.

### Backend language — Python over TypeScript
The original instinct was TS end-to-end (Node backend, single language with the React frontend, sharable types). Reconsidered once team constraints came up: the team is mid Python-course, and the hardest slice of this project — agentic recipes, embeddings, OCR, custom prompt tooling — sits squarely in Python's strongest ecosystem (openai/anthropic SDKs, `pgvector-python`, `pytesseract`, future ML libs). Matching the stack to what the team is actively learning buys real velocity in a 6-week window.

Checked whether Python loses meaningful plumbing compared to the TS picks it replaces — it does not:

| Need | TS pick | Python equivalent | Gap |
|---|---|---|---|
| API framework | Fastify | FastAPI | none — comparable async perf/ergonomics |
| Postgres-native job queue (`SKIP LOCKED`) | pg-boss | Procrastinate | none — same mechanism, actively maintained |
| SSE streaming | Fastify SSE | `sse-starlette` | none |
| pgvector client | drizzle pgvector type | `pgvector-python` | none |
| Agent/LLM tooling | Vercel AI SDK | openai/anthropic SDKs, litellm | Python ecosystem is *deeper* here |
| OCR | Tesseract.js | pytesseract | none |
| Shared FE/BE types | native (same lang) | generate via FastAPI's OpenAPI schema (`openapi-typescript`) | small — one extra build step, not a redesign |

The one real cost is losing free type-sharing between frontend and backend (no shared `.ts` schema). Mitigated by generating the FE's TypeScript client types from FastAPI's auto-generated OpenAPI spec, which is a standard, low-effort pattern.

The browser still forces a JS/TS frontend no matter what — Python cannot render a custom virtualized grid in-browser (Pyodide/WASM is too immature for this). So the stack is unavoidably two languages; the choice was *only* about the backend/worker side.

### Backend framework — FastAPI
Async-first, automatic OpenAPI schema generation (used for FE type generation, see above), first-class SSE support, and the default choice in the Python web ecosystem right now. No reason to reach for Django's heavier batteries-included model for an API-only backend.

### Frontend — React + TS on Vite, not Next.js
This is an internal, auth-gated tool — no SEO or SSR requirement. Next.js's app router adds real friction when the core UI feature is a custom SSE-streamed virtualized grid (fighting server components / hydration boundaries for something that's inherently a client-side live view). A plain Vite + React SPA gives a simpler dev loop and full control over the streaming grid, at no real cost since there's nothing to gain from SSR here.

React itself is the right anchor regardless of backend language, because TanStack Table is React-first (has other framework adapters, but React has the best support) and because React reuses cleanly into a future Tauri desktop wrap.

### DB access — SQLAlchemy 2.0 (async) + raw SQL
The plan is CTE-heavy by design — recursive staleness/lineage walks (`ARCHITECTURE.md` §4), `SELECT … FOR UPDATE SKIP LOCKED`, and `pgvector` similarity queries. ORMs generally handle these awkwardly or not at all. Rather than fight an ORM's abstractions for the queries that matter most, use SQLAlchemy's typed models for the straightforward CRUD (case, row, column, cell reads/writes) and drop to raw SQL for the graph-walk and locking queries. This mirrors the original Drizzle pick's reasoning (raw-SQL escape hatch) translated to Python.

### Job queue — Procrastinate over hand-rolled polling or Redis
The main plan already resolved (§15.5) that Postgres `SKIP LOCKED` is sufficient for pilot scale (~10-15k cells/case) and Redis/Celery is unnecessary until an order-of-magnitude scale jump. Procrastinate *is* that resolution as a library rather than as hand-rolled code — it's a Postgres-native task queue built on `LISTEN/NOTIFY` + `SKIP LOCKED`, giving retries, scheduling, and dead-lettering for free instead of spending 6-week budget reimplementing them.

### Realtime — SSE over WebSocket
The only realtime need is server→client cell-fill streaming into the grid (main plan §4 step 7). SSE is plain HTTP, has automatic reconnect built into `EventSource`, and needs no separate protocol handling — a WebSocket's bidirectional channel would be unused complexity here, since all user actions (adding a recipe, confirming a run) go through normal request/response calls, not a socket.

### LLM access — OpenRouter via the openai SDK
The main plan already fixed OpenRouter as the model gateway (§10). Since OpenRouter exposes an OpenAI-compatible API, the plain `openai` Python SDK pointed at OpenRouter's base URL covers this without adding a dependency — no need for a heavier unifying SDK. If multi-provider routing logic grows more complex later, `litellm` is the fallback option, not a day-one requirement.

### OCR — pytesseract over cloud OCR
The main plan explicitly defers handwriting OCR and bad-quality photos out of P0 (§13) — the real P0 case is a clean official document (e.g. a Prozorro-sourced PDF) that happens to lack a text layer (§7). Tesseract handles that case well, runs locally at no per-page cost, and needs no new vendor key or data-sharing decision. Cloud OCR (Document AI/Textract) stays a documented fallback if week-1 spiking shows Tesseract's accuracy is insufficient even for clean docs.

### File storage — Cloudflare R2
Document blobs (`document.blob_uri` in the main plan's schema) need durable storage outside Postgres. R2 is S3-API-compatible (so the same `boto3` client code ports to AWS S3 later with just a config change), has no egress fees, and is inexpensive at pilot scale — a good fit for a student-budget project.

### Auth — fastapi-users over Clerk/Better-Auth
Better-Auth was the original pick but is TypeScript-only, ruled out once the backend moved to Python. Clerk (hosted/managed) would remove auth plumbing but adds a paid vendor and doesn't map cleanly onto the schema's existing custom `case_member(case_id, user_id, role)` table — reconciling Clerk's org/membership model with a bespoke roles table adds friction rather than removing it. fastapi-users integrates directly with SQLAlchemy, so the existing case-role table stays the source of truth for permissions, with no vendor lock-in and no cost — appropriate for a small, trusted pilot user base.

### Hosting — Railway
Needs: native Postgres with `pgvector` enabled, ability to run multiple services (API + Procrastinate worker) from one deploy, low operational overhead for a student team on a 6-week clock. Railway covers all three with git-based deploys and straightforward secrets management. Fly.io offers more control but requires more Docker/config investment than this timeline justifies; Render is a close second but Railway's multi-service story is a slightly better fit. Revisit post-pilot if scale or cost pushes toward AWS/self-hosted.

### Desktop / mobile — Tauri now, mobile deferred
For the eventual local-PC / private mode (see §3), wrapping the same React build in Tauri (lighter native runtime than Electron, smaller footprint) is the lowest-cost path to a local build that can enforce "no external API calls" at the app level. Mobile is deferred — the grid-based UX doesn't translate well to a small screen, and it's out of scope for the pilot regardless.

---

## 3. Unresolved (flagged, not blocking pilot)

1. **Private mode / external-call gating.** Production is expected to need a mode that blocks all external API calls (LLM providers, WebSearch, YouControl) when operating on private/non-public data, per case or per row. Not yet designed — needs a gating flag in the data model and enforcement point in the recipe execution path. Distinct from the main plan's existing "pilot uses public data only" constraint (§11), which sidesteps this for now but doesn't solve it for production.
2. **Local vs cloud deployment split.** Whether/how the local-PC (Tauri) build and the hosted web build share a backend, run fully independent stacks, or sync — undecided. Directly coupled to the private-mode question above (a local build is the natural enforcement point for "never call external APIs," but only if it can also run recipes locally, which has its own model/compute implications).

Neither blocks the pilot (hosted web, public data only, per main plan §11/§13) but both should be resolved before any production/local-mode work starts.
