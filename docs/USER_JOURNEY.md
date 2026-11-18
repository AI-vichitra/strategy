# User Journey — Complete Walkthrough

Read-only discovery. Every claim below is cited `path/to/file:line`. Where something
could not be confirmed from code, it is marked **not found**. This document covers
PART B (user journey) only — competitor data flow is covered separately in
`docs/COMPETITOR_FLOW.md`.

---

## 1. ASCII journey diagram — happy path, entry → shared report

```
                              ┌─────────────────────┐
                              │   / (landing page)   │
                              │ app/page.tsx:12-54   │
                              └──────────┬───────────┘
                     has access_token?   │ no token → show landing
                     (page.tsx:16-23)    │ token found → router.push('/build')
                                         ▼
                              ┌─────────────────────┐
                              │   /auth              │
                              │ app/auth/page.tsx     │
                              │ login(+ auto-register)│
                              │ OR Google OAuth       │
                              └──────────┬───────────┘
                         routeUserAfterAuth() — auth/page.tsx:81-102
                         GET /api/brands/  → brands.length>0 ? /build
                                 │                              │
                        0 brands, pathChosen set?               │
                         no → /strategy-setup   yes → /brand-setup
                                 │                              │
                                 ▼                              │
                  ┌───────────────────────────┐                │
                  │ /strategy-setup            │                │
                  │ "Choose Your Path"         │                │
                  │ strategy-setup/page.tsx    │                │
                  │ Individual → pathChosen=1  │                │
                  └──────────────┬─────────────┘                │
                                 ▼                              │
   ╔═════════════════════ WIZARD BRANCH ═════════════════════╗ │
   ║ /brand-setup  (brand-setup/page.tsx)                     ║ │
   ║  step='form': brand name, website, category (required), ║ │
   ║    brand context, Brand Kit, inline competitor name+url  ║ │
   ║  CONTINUE → POST /api/brands/search-competitors          ║ │
   ║    (brand.py:51-72, Tavily discovery)                    ║ │
   ║  step='confirm_competitors': select/edit candidates       ║ │
   ║  CONFIRM AND START RESEARCH →                              ║ │
   ║    POST /api/brands/confirm (brand.py:76-138)             ║ │
   ║    creates BrandConfig + Project, launches background      ║ │
   ║    pipeline_service.run_brand_research_pipeline(),         ║ │
   ║    redirects to /build IMMEDIATELY (no polling, no wait)  ║ │
   ╚═══════════════════════════╦═══════════════════════════════╝ │
                                ▼                                 ▼
                  ┌─────────────────────────────────────────────────┐
                  │  /build  (Sidebar + MainContent)                 │
                  │  app/build/page.tsx:5-12                         │
                  │  Sidebar auth-gates itself on mount               │
                  │  (Sidebar.tsx:36-50); MainContent gates per-call  │
                  └──────────────────────┬────────────────────────────┘
                                         │ user picks an agent card
                                         ▼
   ╔═════════════════ CHAT LAZY-CREATE BRANCH ═══════════════════╗
   ║ messages.length===0 && selectedAgent:                        ║
   ║  onboardingForms: BrandKitForm + CompetitorForm (name+url+    ║
   ║  social URLs, max 5) + optional AgentQuestionnaire             ║
   ║  (MainContent.tsx:1827-1843)                                  ║
   ║  First submit with no project → POST /api/projects/           ║
   ║  (MainContent.tsx:1173-1190) creates Project directly,         ║
   ║  competitor_details + brand_kit stored on THIS project only   ║
   ╚════════════════════════════╦══════════════════════════════════╝
                                 ▼
                  ┌─────────────────────────────────────────────┐
                  │ POST /api/chat/  (SSE stream)                │
                  │ chat.py:31-61 → ai_service.stream_chat        │
                  │ tokens render live; "thinking" placeholder    │
                  │ (MainContent.tsx:1139, 1241-1280)              │
                  └──────────────────────┬────────────────────────┘
                     full_response qualifies? chart_count>=1 OR
                     heading_count>=3 (ai_service.py:2682)
                         │ yes                        │ no
                         ▼                             ▼
          Report row created                 chat message only —
          (report_service.create_          NO download/share/edit
          report_snapshot)                  buttons ever appear
                         │                   for this message
                         ▼
          ReportRenderer renders accordion (###-split, first 2 H3s
          always visible) + recharts blocks (ReportRenderer.tsx)
                         │
          ┌──────────────┼───────────────────────┐
          ▼              ▼                       ▼
   Export (PDF/DOCX/   Edit Sections         Share → POST
   PPTX) — ALL raw,    (SectionEditor.tsx)   /api/reports/{id}/share
   unedited content    only its own "Export  → token → /r/[token]
   (GET endpoints)      DOCX" button honours  public page, read-only,
                        edits (POST+content)  no auth, no export/edit
```

---

## 2. Step table

| Step | Route | Component (file:line) | API calls | What persists | What the user sees on failure |
|---|---|---|---|---|---|
| Landing | `/` | `app/page.tsx:12-54` | none (checks `localStorage.access_token`, [page.tsx:17](frontend/src/app/page.tsx#L17)) | nothing | n/a — static page |
| Sign in / register | `/auth` | `app/auth/page.tsx:7-187` | `POST /api/auth/login` → on 401/404/400/422 falls back to `POST /api/auth/register` ([page.tsx:28-58](frontend/src/app/auth/page.tsx#L28-L58)); `GET /api/brands/` in `routeUserAfterAuth` ([page.tsx:81-102](frontend/src/app/auth/page.tsx#L81-L102)) | `access_token` in `localStorage` ([page.tsx:50,65](frontend/src/app/auth/page.tsx#L50)) | inline `error` string set from caught exception message ([page.tsx:77](frontend/src/app/auth/page.tsx#L77)); no field-level validation beyond HTML `required` |
| Google sign-in | `/auth` | `app/auth/page.tsx:104-123` | `POST /api/auth/google` ([page.tsx:108](frontend/src/app/auth/page.tsx#L108)) → `backend/routers/auth.py:73-108` (verifies Google ID token, creates `User` if new with a random bcrypt-hashed placeholder password) | `access_token` in `localStorage` | `GoogleLogin onError` → generic "unsuccessful" message ([page.tsx:125-127](frontend/src/app/auth/page.tsx#L125-L127)) |
| Tier choice | `/strategy-setup` | `app/strategy-setup/page.tsx:7-119` ("TierSelection" component) | none | `localStorage.pathChosen='true'` ([page.tsx:21](frontend/src/app/strategy-setup/page.tsx#L21)) | Enterprise card is an `alert()`, not a real flow ([page.tsx:25-27](frontend/src/app/strategy-setup/page.tsx#L25-L27)) |
| Brand wizard form | `/brand-setup` (`step='form'`) | `app/brand-setup/page.tsx:8-583` (internal function named `StrategySetupInner` — confusingly, the reverse of the `/strategy-setup` route's "TierSelection") | `POST /api/brands/search-competitors` on CONTINUE ([page.tsx:144-153](frontend/src/app/brand-setup/page.tsx#L144-L153)) | nothing yet — brand/project not created until confirm | inline required-field errors with scroll-to ([page.tsx:124-129](frontend/src/app/brand-setup/page.tsx#L124-L129)); on request failure, `alert()` + reverts to form step ([page.tsx:174-178](frontend/src/app/brand-setup/page.tsx#L174-L178)); a `tavilyError` banner is shown but doesn't block ([page.tsx:438-448](frontend/src/app/brand-setup/page.tsx#L438-L448)) |
| Competitor review | `/brand-setup` (`step='confirm_competitors'`) | same file, 420-567 | `POST /api/brands/confirm` on final confirm ([page.tsx:195-214](frontend/src/app/brand-setup/page.tsx#L195-L214)) → `backend/routers/brand.py:76-138` | Creates `BrandConfig` + default `Project` rows; `background_tasks.add_task(pipeline_service.run_brand_research_pipeline, ...)` ([brand.py:128-136](backend/routers/brand.py#L128-L136)); `localStorage.brand_config_id` set ([page.tsx:223](frontend/src/app/brand-setup/page.tsx#L223)) | "Please select or add at least one competitor" alert if none selected ([page.tsx:183-186](frontend/src/app/brand-setup/page.tsx#L183-L186)); on confirm failure, `alert()`, user stays on this step |
| Redirect, pipeline runs | `/build` | n/a | none from the frontend — `GET /api/brands/{id}/status` exists ([brand.py:142-162](backend/routers/brand.py#L142-L162)) but **is never called anywhere in `frontend/src`** (confirmed by repo-wide search) | pipeline writes to KNOWLEDGE_BASE on disk and updates `BrandConfig.pipeline_status` server-side, invisible to the UI | none — user is not blocked, polled, or notified; failure is silent from the UI's perspective |
| Chat home / agent pick | `/build` | `components/builder/MainContent.tsx:1753-1797` renders `TemplateGrid` cards ([TemplateGrid.tsx:233-249](frontend/src/components/builder/TemplateGrid.tsx#L233-L249)) | `GET /api/agents` via `useAgents()` ([useAgents.ts:42-53](frontend/src/hooks/useAgents.ts#L42-L53)) | `selectedAgent` client state only | skeleton cards while loading, explicit error state + Retry button ([TemplateGrid.tsx:218-225](frontend/src/components/builder/TemplateGrid.tsx#L218-L225)) |
| Onboarding forms | `/build` | `MainContent.tsx:1827-1843` — `BrandKitForm` + `CompetitorForm` + optional `AgentQuestionnaire` | logo upload: `POST /api/projects/upload-logo` ([projects.py:55-71](backend/routers/projects.py#L55-L71)) | held in React state (`brandKit`, `competitors`) until first chat submit | n/a (local form) |
| First chat submit (lazy project create) | `/build` | `MainContent.tsx:1171-1202` | `POST /api/projects/` with `competitor_details` + `brand_kit` ([MainContent.tsx:1173-1190](frontend/src/components/builder/MainContent.tsx#L1173-L1190)) → `backend/routers/projects.py:74-106` | New (or reused, if an existing 0-message project for the brand exists — [projects.py:79-98](backend/routers/projects.py#L79-L98)) `Project` row; `competitor_details` capped at 5 ([projects.py:21,39-40](backend/routers/projects.py#L21)) | none shown beyond the generic chat error path below |
| Generation (SSE) | `/build` | `MainContent.tsx:1212-1302` | `POST /api/chat/` ([MainContent.tsx:1212-1220](frontend/src/components/builder/MainContent.tsx#L1212-L1220)) → `backend/routers/chat.py:31-61` → `ai_service.stream_chat` | user+assistant `Message` rows saved only on a *successful* generation ([ai_service.py:2622-2638](backend/services/ai_service.py#L2622-L2638)); conditionally a `Report` snapshot (`chart_count>=1 or heading_count>=3`, [ai_service.py:2681-2694](backend/services/ai_service.py#L2681-L2694)) | mid-stream `type:'error'` SSE event → inline error message, project reset if no text yet ([MainContent.tsx:1268-1277](frontend/src/components/builder/MainContent.tsx#L1268-L1277)); `res.status===401` → token cleared, hard redirect to `/auth` ([MainContent.tsx:1222-1228](frontend/src/components/builder/MainContent.tsx#L1222-L1228)); network-level failure → "Could not connect to backend..." message ([MainContent.tsx:1296-1301](frontend/src/components/builder/MainContent.tsx#L1296-L1301)) |
| Report view | `/build` | `components/ReportRenderer.tsx` | none (renders already-fetched message content) | n/a | 3 `ChartFallbackCard` cases: unsupported chart type ([ReportRenderer.tsx:408-411](frontend/src/components/ReportRenderer.tsx#L408-L411)), no chart data ([ReportRenderer.tsx:414-417](frontend/src/components/ReportRenderer.tsx#L414-L417)), JSON parse/render exception ([ReportRenderer.tsx:984-985](frontend/src/components/ReportRenderer.tsx#L984-L985)); plus a separate `ChartErrorBoundary` catching React-level render throws ([ReportRenderer.tsx:276-310](frontend/src/components/ReportRenderer.tsx#L276-L310)) |
| Edit sections | `/build` (overlay) | `components/SectionEditor.tsx:109-526` | `GET …/sections`, `POST …/sections/parse`, `POST …/sections`, `PUT …/sections/{id}`, `DELETE …/sections/{id}`, `PUT …/sections/reorder` ([useSections.ts:54-106](frontend/src/hooks/useSections.ts#L54-L106)) | `ReportSection` rows (order, title, content, visible) | `error` banner per action, falls back to full reload on reorder failure ([SectionEditor.tsx:178-184](frontend/src/components/SectionEditor.tsx#L178-L184)) |
| Export | `/build` | `components/ExportMenu.tsx` + handlers in `MainContent.tsx:636-806` | `GET /api/reports/{id}/export/{pdf,docx,pptx}` — **all render `report.content` raw**, unaffected by section edits ([reports.py:109-117](backend/routers/reports.py#L109-L117) docx docstring, [135-152](backend/routers/reports.py#L135-L152) pptx, [154-179](backend/routers/reports.py#L154-L179) pdf) | nothing new persisted | per-row spinner + "Failed" chip in `ExportMenu` ([ExportMenu.tsx:174-177](frontend/src/components/ExportMenu.tsx#L174-L177)) |
| Export (section-aware) | SectionEditor overlay only | `SectionEditor.tsx:301-330` | `POST /api/reports/{id}/export/docx` with `{content: getFinalizedContent()}` — **the only export path that honours section edits** ([reports.py:119-133](backend/routers/reports.py#L119-L133)) | nothing new persisted | `alert('Failed to export DOCX...')` ([SectionEditor.tsx:325-326](frontend/src/components/SectionEditor.tsx#L325-L326)) |
| Share | `/build` → `/r/[token]` | `MainContent.tsx` `handleShareReport` (defined at [MainContent.tsx:813](frontend/src/components/builder/MainContent.tsx#L813)) | `POST /api/reports/{id}/share` ([reports.py:181-186](backend/routers/reports.py#L181-L186)) | `ReportShare` row with a `secrets.token_urlsafe(32)` token ([share_service.py:39](backend/services/share_service.py#L39)) | "Failed to create share link" inline text ([MainContent.tsx:1611-1615](frontend/src/components/builder/MainContent.tsx#L1611-L1615)) |
| Public view | `/r/[token]` | `app/r/[token]/page.tsx:15-117` | `GET /api/public/reports/{token}` — no auth header ([page.tsx:37](frontend/src/app/r/[token]/page.tsx#L37)) → `backend/routers/public.py:17-22` | nothing | "Report not found" state on 404/network error ([page.tsx:77-93](frontend/src/app/r/[token]/page.tsx#L77-L93)); renders `report.content` **raw**, same as the GET export endpoints — section edits are not reflected here either ([share_service.py:76](backend/services/share_service.py#L76) selects `Report` row directly, no section merge) |

---

## 3. Divergences — wizard path vs chat lazy-create path

| Aspect | Wizard (`/brand-setup` → `POST /api/brands/confirm`) | Chat lazy-create (`POST /api/projects/`) |
|---|---|---|
| Competitor input UI | Raw inline `<input>` pair, name + optional URL, added as chips ([brand-setup/page.tsx:350-393](frontend/src/app/brand-setup/page.tsx#L350-L393)) — **does not use** the `CompetitorForm` component at all | Dedicated `CompetitorForm` component ([MainContent.tsx:1831](frontend/src/components/builder/MainContent.tsx#L1831)) — also captures per-competitor social media URLs (`CompetitorSocialMedia`: linkedin/instagram/facebook/twitter/youtube — [schemas/project.py:18-28](backend/schemas/project.py#L18-L28)) |
| Competitor count cap | None found in `BrandConfirmRequest`/`BrandSearchRequest` (`backend/schemas/brand.py`) — no `max_length` on `selected_competitors` | Hard cap of 5, enforced server-side with a `422` ([projects.py:21,39-40](backend/routers/projects.py#L21)) |
| Auto-discovery | Runs Tavily via `POST /api/brands/search-competitors` before the user ever confirms anything ([brand.py:51-72](backend/routers/brand.py#L51-L72)) | None — the chat path has no equivalent discovery step; competitors are only what the user types into `CompetitorForm` |
| Where it lands | `BrandConfig.competitors` (JSON string, `{name, url}` pairs only — social fields dropped even if present) ([brand.py:93-104](backend/routers/brand.py#L93-L104)) | `Project.competitor_details` (JSON string of full `CompetitorDetail` objects including `social_media`) ([projects.py:76,93,102](backend/routers/projects.py#L76)) |
| Brand Kit | Collected via `BrandKitForm` in the form step ([brand-setup/page.tsx:346](frontend/src/app/brand-setup/page.tsx#L346)), sent once at confirm | Same `BrandKitForm` component, but attached to the lazily-created `Project` directly at first chat submit ([MainContent.tsx:1185-1188](frontend/src/components/builder/MainContent.tsx#L1185-L1188)) |
| Research pipeline | Launched automatically as a background task on confirm ([brand.py:128-136](backend/routers/brand.py#L128-L136)) | Not triggered at all by `POST /api/projects/` — **not found** anywhere that the chat path invokes `pipeline_service.run_brand_research_pipeline` |
| Onboarding MCQs | None in this path | `AgentQuestionnaire` shown conditionally, see §5 below |

---

## 4. Friction & dead ends

- **Dead component — `AgentsPanel.tsx`.** Fully built (open/close, category tabs, search — [AgentsPanel.tsx:41-195](frontend/src/components/builder/AgentsPanel.tsx#L41-L195)) but never imported anywhere in `frontend/src` (confirmed by repo-wide search for `AgentsPanel`). The `openAgents` event it would presumably respond to is instead wired to `setView('agents')`, which renders `TemplateGrid` ([MainContent.tsx:1096,1458-1459](frontend/src/components/builder/MainContent.tsx#L1096)).
- **Onboarding MCQs mostly unreachable for the real catalog.** The questionnaire shown is a hardcoded `agentQuestions` object keyed by exact agent title string ([MainContent.tsx:25](frontend/src/components/builder/MainContent.tsx#L25)), with 23 keys. The live registry (`backend/data/agents_registry.json`, 31 enabled agents) only exactly matches **10** of those keys (`GTM Strategy`, `Product Launch Strategy`, `Social Media Strategy`, `Content Calendar`, `Seasonal Campaign`, `GEO/AEO`, `Brand Audit`, `Campaign Structure Architect`, `ICP & Personas`, `Bidding & Budget Optimizer`). The other 21 registry agents (e.g. `Competition Analysis`, `SEO Strategy`, `Brand Positioning`, `Company Research Agent`, `Email Marketing`, `Compliance & Legal`, …) get **no** onboarding questionnaire at all when selected, because `showQuestionnaire = !!agentQuestions[title]` ([MainContent.tsx:994](frontend/src/components/builder/MainContent.tsx#L994)) never matches. Conversely, 13 hardcoded keys (`SEO Audit`, `Festival Campaign`, `Topical Campaign`, `Trend Strategy`, `SEO`, `Business Plan Generator`, `Partnership & Distribution Strategy`, `Revenue Model Strategy`, `Market Sizing & Entry`, `Attribution & Measurement Agent`, `Legal Agreement Drafter`, `Brand Personality and Guidelines`, `Competitor Research Agent`) don't correspond to any title in the registry and are unreachable dead code.
- **Backend questionnaire endpoint is unused.** `GET /api/chat/questions/{title}` ([chat.py:17-27](backend/routers/chat.py#L17-L27)), which reads `registry_service.get_questions()` (3 free-text questions per agent, [registry_service.py:69-74](backend/services/registry_service.py#L69-L74)), is never called from `frontend/src` (confirmed by repo-wide search for `questions/`). The registry's own questions data is written but never read by the UI.
- **Pipeline status endpoint is unused.** `GET /api/brands/{brand_id}/status` ([brand.py:142-162](backend/routers/brand.py#L142-L162)) is never called from the frontend. After `POST /api/brands/confirm`, the user is redirected straight to `/build` with zero visibility into whether Tavily/Firecrawl/the social scraper succeeded.
- **"Share This Agent" modal is cosmetic.** Opened by the top-bar Share button ([MainContent.tsx:1439](frontend/src/components/builder/MainContent.tsx#L1439) → `shareOpen`), its copy talks about letting "other users... chat with it and edit its configuration" ([MainContent.tsx:1871](frontend/src/components/builder/MainContent.tsx#L1871)), but the "Add people" input and "Share" button have no `onClick`/submit handler at all ([MainContent.tsx:1874-1880](frontend/src/components/builder/MainContent.tsx#L1874-L1880)) — nothing happens. This is distinct from the real, working per-report Share flow (`handleShareReport`, §2 above).
- **`FilesView` has no backend of its own.** "Files" are synthesized client-side from `GET /api/projects/` message history ([FilesView.tsx:43-113](frontend/src/components/builder/FilesView.tsx#L43-L113)); there is no `files` router. Its PDF download uses a separate client-side HTML→canvas export (`utils/pdfExport.ts`, via `exportReportToPdf`), not the backend's LibreOffice-based `/export/pdf`. Every synthesized file has `shared: false` hardcoded ([FilesView.tsx:100](frontend/src/components/builder/FilesView.tsx#L100)), so the **"Shared" tab is permanently empty** — a dead end built into the filter itself ([FilesView.tsx:152-153](frontend/src/components/builder/FilesView.tsx#L152-L153)).
- **`WorkflowView` is a non-functional placeholder.** Static stats and copy only; its "Create Workflow" button has no handler ([WorkflowView.tsx:68-73](frontend/src/components/builder/WorkflowView.tsx#L68-L73)).
- **Most connector cards don't do anything downstream.** `ConnectorsView.tsx:8-45` lists ~80 connector names across 3 categories. Credentials saved via `POST /api/connectors` are only ever read back by `connector_service.get_api_key` in two call sites: `pipeline_service.py:85` (Firecrawl) and `pipeline_service.py:98` (Exa). No other service in `backend/services` reads a stored connector credential for any of the remaining ~78 integrations (Slack, Notion, HubSpot, Google Analytics, GitHub, etc.) — confirmed by searching for `connector_service.get_api_key`/`get_credentials` call sites. They can be "Connected" and stored, but nothing in the pipeline or chat generation consumes them.
- **No settings page/route exists** anywhere under `frontend/src/app` or `frontend/src/components` (confirmed by search for `settings`).
- **"Incognito toggle mode" is marketing copy only.** Advertised on `/strategy-setup` ([strategy-setup/page.tsx:65](frontend/src/app/strategy-setup/page.tsx#L65)) but not found anywhere else in `frontend/src`.
- **`ProjectsView` never handles a 401.** Unlike `Sidebar.tsx` (which explicitly checks `res.status===401` and redirects, [Sidebar.tsx:46-50](frontend/src/components/builder/Sidebar.tsx#L46-L50)), `ProjectsView.tsx`'s `fetchProjects`/rename/delete calls only check `res.ok` or log to console on `catch` — an expired token here fails silently with no redirect and no visible error (confirmed: no `401` string anywhere in `ProjectsView.tsx`).
- **`/brand-setup?new=true` skips its own auth check.** `checkFirstTimeUser` returns immediately without reading `access_token` when `isNewProject` is true ([brand-setup/page.tsx:16-19](frontend/src/app/brand-setup/page.tsx#L16-L19)), so an unauthenticated visitor can load and fill out the entire multi-step wizard UI; the 401 wall only appears when `handleSubmit` actually calls `search-competitors` ([brand-setup/page.tsx:155-159](frontend/src/app/brand-setup/page.tsx#L155-L159)).
- **Route protection is entirely client-side, everywhere.** No `middleware.ts` exists under `frontend/` (confirmed by search), and `app/layout.tsx:16-26` applies no auth gate. Every page checks `localStorage.access_token` in a `useEffect`/data-fetch callback after the component has already started rendering ([page.tsx:16-23](frontend/src/app/page.tsx#L16-L23), [brand-setup/page.tsx:14-48](frontend/src/app/brand-setup/page.tsx#L14-L48), [strategy-setup/page.tsx:11-18](frontend/src/app/strategy-setup/page.tsx#L11-L18), [Sidebar.tsx:33-50](frontend/src/components/builder/Sidebar.tsx#L33-L50)), so `/`, `/build`, `/brand-setup`, `/strategy-setup` all paint at least a loading/shell frame before any redirect can fire. `GET /api/agents` ([agents.py:9-14](backend/routers/agents.py#L9-L14)) has no `get_current_user` dependency at all and is reachable with zero auth.

---

## 5. Gaps vs intended journey

The task's framing is "name + URL + 3 clicks → board-ready report." Tracing the actual
click/step count for a first-time user:

1. Landing → click a CTA → `/auth` (1 click)
2. Register/login (1 submit) or Google OAuth (1 click)
3. `/strategy-setup` → click "Get Started" (1 click)
4. `/brand-setup` form → fill brand name + website + category (mandatory, [brand-setup/page.tsx:125-127](frontend/src/app/brand-setup/page.tsx#L125-L127)) → click CONTINUE (1 click, triggers Tavily)
5. Review/confirm competitors screen → click CONFIRM AND START RESEARCH (1 click) → redirected to `/build`
6. At `/build`, the background pipeline (Tavily/Firecrawl/social scraping) runs with **no visible progress, no completion signal** (the `/status` endpoint is unused, §4) — the user has no way to know when it's done
7. The user must then separately **pick an agent card**, fill the onboarding forms again (`CompetitorForm`/`BrandKitForm` reappear per-agent, §3), and **type and submit a chat prompt** to actually generate anything (1+ clicks/typing)
8. The generated chat response only becomes a downloadable/shareable "report" if it happens to contain `chart_count>=1 or heading_count>=3` ([ai_service.py:2682](backend/services/ai_service.py#L2682)) — otherwise the user gets a plain chat message with no export/share/edit affordance at all, and no indication *why* (no messaging references the chart/heading thresholds anywhere in the frontend; confirmed no `chart_count`/`heading_count` string in `frontend/src`)

So reaching a "board-ready report" takes at minimum 6 clicks plus two rounds of form-filling
(brand/competitor info once at setup, then brand kit/competitor info again per agent) plus an
unsignaled wait for a background pipeline, plus a non-obvious content-shape gate the user is
never told about. The "3 clicks" framing does not match what the code does.

Other gaps:
- The wizard's own research pipeline (Tavily discovery, Firecrawl/Exa scraping, social handles)
  is **not reused or referenced** by the chat lazy-create path at all — a user who skips the
  wizard and goes straight into a chat gets zero automated competitor research, only whatever
  they typed into `CompetitorForm`.
- Section edits made in `SectionEditor` are invisible everywhere except that editor's own
  "Export DOCX" button — the main `ExportMenu` (PDF/DOCX/PPTX) and the public `/r/[token]` share
  page both always render the original, unedited `report.content` (§2, §4). A user who edits,
  hides, or reorders sections and then uses the ordinary export/share buttons will not see their
  changes reflected anywhere a reader can actually consume.
- PPTX and PDF exports have **no section-aware variant at all** — only DOCX has one
  ([reports.py:109-179](backend/routers/reports.py#L109-L179): compare the docx GET/POST pair
  against the single GET-only pptx/pdf routes).

---

## 6. Questions for Moody

1. Is `GET /api/brands/{brand_id}/status` meant to be wired into the frontend (e.g. a polling
   spinner on `/build` after confirm), or is it dead/legacy? It exists and has a complete
   response schema but is called from nowhere in `frontend/src`.
2. Is `AgentsPanel.tsx` a superseded earlier version of the agent-picker UI (before
   `TemplateGrid`), safe to delete, or is something still supposed to mount it?
3. Is the mismatch between the hardcoded `agentQuestions` keys in `MainContent.tsx` and the
   actual `agents_registry.json` titles a known/accepted gap, or should the questionnaire be
   driven from the registry (via the already-built but unused `GET /api/chat/questions/{title}`)
   instead of a hardcoded per-title table?
4. Is the "Share This Agent" modal (collaborator sharing, with an "Add people" field) a planned
   feature that just hasn't been wired up yet, or leftover copy that should be removed to avoid
   confusing it with the real per-report Share link?
5. Should PPTX/PDF export gain a section-aware (POST + edited content) variant to match DOCX, or
   is "edits only affect DOCX export" an intentional scope limit for now?
6. Most of the ~80 connector entries in `ConnectorsView` can be "Connected" and store credentials
   but are never read by any backend service — is that catalog meant to signal a roadmap, or
   should it be trimmed to the integrations that are actually wired up (currently just Firecrawl
   and Exa)?
7. Is `/brand-setup?new=true` intentionally allowed to render for an unauthenticated visitor
   (relying on the eventual 401 from `search-competitors`), or should it check `access_token`
   up front the way the `isNewProject=false` branch of the same effect already does?
