# StratAI — The Full Picture

Architecture, runtime flow, and contracts, reconciled from:

| Doc | What it actually contributes |
|---|---|
| `Strategy_Tools_brief_RESEARCH.docx` | Competitor teardown (Blaze, GravityWrite, MindPal, Relevance AI, Gumloop, Klue, AlphaSense). The canonical **13-element GTM structure**. The product thesis: *fixed output format, minimal user input*. |
| `AGENTS_and_CATEGORIES.docx` | The **24-agent taxonomy** by category + tier. The **2–4 essential questions per agent** with exact option lists. The **connector → agent** mapping per category. The strategy framework library (Brand Pyramid, CEPs, PESTLE, Porter, TAM/SAM/SOM, Ansoff, TOWS, BMC, VPC, MEDDIC, AARRR). |
| `Final_Agents_Prompts_Categories.docx` | Category→agent catalog with Gumloop/MindPal prompt bodies. The **reverse connector index ranked by coverage** (Firecrawl 14 agents, Exa 12, Google Docs 9…). Two elite long-form prompt templates (Tab 3 variable-driven, Tab 4 strict-markdown). |
| `Master_Prompt.docx` | Production master prompts for **Competition Analysis** and **GTM Strategy**. The **global STRICT OUTPUT RULES**. And — most important — a **real assembled runtime prompt**, showing the exact `=== RESEARCH CONTEXT === / [Source N — Name — Type]` envelope the model actually receives. |

---

## 1. What the product is, in one paragraph

A user signs in and gives two things: **company name + URL**. Nothing else. They pick an agent from a category grid (SEO Audit, GTM Strategy, Brand Positioning…). The agent asks **2–4 multiple-choice questions** — never a free-text brief. The system then fans out to connectors (crawl the site, scrape Instagram, pull competitors, query GSC/Ahrefs), normalizes everything into a brand knowledge base, composes a four-block prompt, streams a **board-ready Markdown report with live inline charts**, and persists it. The user's total typing is: a name, a URL, and three clicks.

The moat is not the LLM. It is the **combination of (a) minimal input, (b) deterministic output format, (c) a reusable brand knowledge base shared across all 24 agents.**

---

## 2. The one architectural decision everything else follows from

> **An agent is data, not code.**

There is exactly **one** execution pipeline. All 24 agents are JSON/TS config objects fed into it. Adding agent #25 is a config file and zero pipeline changes.

If you instead build 24 code paths — one route, one prompt file, one question form per agent — the project dies at around agent 8. Every global change (a new forbidden phrase, a new chart type, a token-budget fix) becomes 24 edits, and the agents silently drift out of sync.

Everything in this document is in service of keeping the pipeline singular and the agents declarative.

```
                        ┌──────────────────────────────┐
  24 agent configs ───► │   ONE generic run pipeline    │ ───► report
  (pure data)           └──────────────────────────────┘
                                      ▲
                        shared: prompt composer, research
                        fan-out, token budgeter, validator,
                        renderer, export
```

---

## 3. System layers

```
L0  IDENTITY        org, user, brand (name + URL captured at signup)
L1  CATALOG         categories → 24 agent configs (declarative)
L2  INTAKE          2–4 schema-driven questions, rendered by ONE component
L3  RESEARCH        connector fan-out → normalized EvidenceDoc[]
L4  KNOWLEDGE       brand knowledge base — cached, versioned, SHARED across agents
L5  COMPOSITION     4-block prompt assembly + token budgeting
L6  GENERATION      streaming LLM call
L7  VALIDATION      structural gate + targeted repair pass
L8  RENDER          markdown + ```recharts interception
L9  PERSIST         report storage, versioning, export (PDF / DOCX / Slides)
```

L4 is the layer that most teams skip and most regret skipping. SEO Audit, Brand Audit, Competition Analysis and Topical Strategy all need the same site crawl. Crawl once, reuse eleven times.

---

## 4. Runtime flow

```
 USER                 FRONTEND              BACKEND                CONNECTORS         LLM
  │                      │                     │                        │              │
  ├─ signup: name+URL ──►│                     │                        │              │
  │                      ├── POST /brands ────►│                        │              │
  │                      │                     ├── enqueue profile job ─┤              │
  │                      │                     │   crawl site ─────────►│              │
  │                      │                     │◄── EvidenceDoc[] ──────┤              │
  │                      │                     ├── extract BrandProfile ──────────────►│
  │                      │                     │◄───────────────────────────────────── │
  │                      │                     │   (cached — reused by every agent)    │
  │                      │                     │                        │              │
  ├─ pick "SEO Audit" ──►│                     │                        │              │
  │                      ├── GET /agents/seo-audit  (config)            │              │
  │◄─ 3 questions ───────┤                     │                        │              │
  ├─ 3 clicks ──────────►│                     │                        │              │
  │                      ├── POST /runs ──────►│                        │              │
  │                      │◄── {runId} ─────────┤                        │              │
  │                      │                     │                        │              │
  │                      ├═══ SSE /runs/:id/stream ═══════════════════════════════════ │
  │                      │                     │                        │              │
  │◄─ "Crawling site"  ──┤◄── stage:RESEARCH ──┤── firecrawl ──────────►│              │
  │◄─ "Checking GSC"   ──┤◄── stage:RESEARCH ──┤── gsc, ahrefs ────────►│              │
  │                      │                     │◄── EvidenceDoc[] ──────┤              │
  │                      │                     ├── rank + budget to 60k tokens         │
  │                      │                     ├── compose 4 blocks                    │
  │◄─ "Writing report" ──┤◄── stage:SYNTH ─────┤──────────────────────────────────────►│
  │◄─ markdown tokens ───┤◄══ token stream ════╡◄══════════════════════════════════════╡
  │   (charts render     │                     │                        │              │
  │    as fences close)  │                     ├── VALIDATE ────────────┤              │
  │                      │                     ├── repair pass if needed ─────────────►│
  │◄─ complete ──────────┤◄── stage:DONE ──────┤── persist report       │              │
```

**Timings to design for:** research 20–90s, synthesis 40–120s. Total 1–4 minutes. This *must* be an async job with a live stage timeline. A spinner for three minutes is a churned user; a stage timeline that says "Analyzing 47 pages from yourbrand.com" is a product feature.

---

## 5. Prompt composition contract

Four blocks, assembled in this exact order. This is lifted directly from the working example in `Master_Prompt.docx`.

```
┌─ BLOCK 1 ── SYSTEM_CORE ────────────────────── shared by ALL 24 agents
│  • Identity: "You operate inside an automated strategy tool."
│  • STRICT RESPONSE OUTPUT RULES (no preamble/postamble/jargon/fake links)
│  • Chart contract (```recharts schema + the 5 allowed types)
│  • Missing-data rule: "Data not available" — never explain why
│  ONE FILE. Changing it changes all 24 agents at once.           [CACHEABLE]
│
├─ BLOCK 2 ── AGENT_ROLE ─────────────────────── per agent, from config
│  • Persona + seniority ("Senior Competitive Intelligence Strategist, 15+ yrs")
│  • Objective
│  • Required section outline (enforced later by the validator)
│  • Required visuals (which chart, which type, what it must contain)
│  • Framework hints (TOWS, CEPs, TAM/SAM/SOM…)
│
├─ BLOCK 3 ── BRAND_CONTEXT ──────────────────── per brand + this run
│  • Brand name, URL, category, positioning (from cached BrandProfile)
│  • THE USER'S 2–4 ANSWERS, as labeled facts:
│      Primary SEO objective: More Leads
│      Biggest SEO challenge: Technical SEO Issues
│      Priority keywords: AI Marketing, CRM Software
│                                                                  [CACHEABLE]
│
└─ BLOCK 4 ── RESEARCH_CONTEXT ───────────────── per run, token-budgeted
   === RESEARCH CONTEXT ===
   [Source 1 — yourbrand.com — Deep Intelligence Report]
   <normalized text>

   [Source 2 — competitor.com — Deep Intelligence Report]
   <normalized text>

   [Source 3 — @competitor — Instagram Social Analysis]
   <normalized text>
   === END CONTEXT ===
```

**Blocks 1 and 3 are prompt-cache anchors.** Put them first and keep them byte-stable across runs for the same brand. A user running six agents against one brand pays full price once and cached price five times. On Opus-class models this is the difference between a viable unit economic and an unviable one.

**Block 4 is never a blind concatenation.** Rank evidence by relevance to `(agent.id + user answers)`, then truncate to budget. Blind-concatenating six competitor scrapes will blow the window and, worse, bury the signal.

---

## 6. The chart contract — and the conflict you need to resolve

Your docs contain **three different chart formats**. They cannot all ship.

| Source | Format |
|---|---|
| `Master_Prompt.docx` §Competition Analysis | ` ```recharts ` with `{type, title, data}` |
| `Master_Prompt.docx` §Section 2 | `DASHBOARD VISUAL (BAR):` marker + ` ```json ` with `{chart_type, x_axis, series}` |
| `Final_Agents…docx` Tab 4 | **No JSON at all** — ASCII `#` proportional bars, explicitly "no code blocks" |

The rendered screenshot in `Master_Prompt.docx` settles it: the UI shows a **`DASHBOARD VISUAL (BAR)` pill above a live Recharts chart**. So:

**Decision — standardize on one wire format, derive the pill from it:**

````
```recharts
{
  "type": "bar",                    // bar | line | area | radar | pie  (REQUIRED)
  "title": "2024 Revenue Comparison (USD Billions)",
  "data": [ {"name": "PepsiCo", "value": 91}, ... ],
  "keys": ["Revenue", "Users"]      // multi-series only (line/area/radar)
}
```
````

- The renderer prints the pill `DASHBOARD VISUAL (BAR)` from `type`. The LLM never writes the marker — one less thing it can get wrong.
- `chart_type` / `x_axis` / `series` from the second format are **dropped**. Normalize in the parser if legacy reports exist.
- Tab 4's ASCII-bar style is **not** a competing output format. It becomes the **`plain-text` render profile** used for PDF/DOCX export and for e-mail delivery where Recharts cannot run. Same JSON, different renderer.

**Enforced invariants** (checked by the validator, not hoped for):
- `type` present and in the allowed set
- `data` non-empty, every entry has `name`
- `pie` → values sum to 100 (±1)
- `radar` → every entry has `subject` + every key in `keys`
- agent's `requiredVisuals` all present

---

## 7. Data model

Postgres + Prisma. Current `KNOWLEDGE_BASE/` becomes blob storage for raw payloads; the index moves into the DB.

```
organizations ──┬── users
                └── brands ──┬── brand_profiles      (versioned, extracted)
                             ├── brand_competitors   (self-ref)
                             ├── evidence_documents  (THE CACHE)
                             └── agent_runs ──┬── agent_run_sources (→ evidence)
                                              └── reports ── report_exports
connector_accounts (org, provider, encrypted creds, status, quota)
```

**`evidence_documents`** — the table that makes the economics work:

```
id, brand_id, provider, kind, url, title,
content_text, content_hash, raw_blob_path,
metadata jsonb, confidence,
fetched_at, expires_at
UNIQUE (brand_id, provider, kind, content_hash)
INDEX  (brand_id, provider, expires_at)
```

TTLs by volatility: site crawl 7d · Instagram 3d · SERP 1d · GSC/Ahrefs 1d · company profile 30d.

**`agent_runs`** — `status`, `stage`, `answers jsonb`, `model`, `prompt_tokens`, `cached_tokens`, `completion_tokens`, `cost_usd`, `error`, timestamps. You need `cached_tokens` separately or you cannot prove the caching strategy is working.

**`agent_run_sources`** — which evidence docs were *actually included* after budgeting, with rank. This is your audit trail when a user asks "where did this number come from", and it is what makes per-claim source attribution possible later.

---

## 8. Connector layer

Every connector implements one interface. `web_scrapper/` and `social_scrapper/` become the first two implementations rather than standalone scripts.

```python
class Connector(Protocol):
    provider: str                      # "firecrawl" | "instagram" | "exa" | ...
    kinds: list[str]                   # "site_crawl" | "profile_posts" | ...
    async def fetch(self, req: FetchRequest) -> list[EvidenceDoc]: ...
    def health(self) -> HealthStatus: ...
```

```python
@dataclass
class EvidenceDoc:
    source_id: str
    source_name: str        # "yourbrand.com" | "@competitor"
    source_type: str        # "Deep Intelligence Report" | "Instagram Social Analysis"
    url: str | None
    title: str
    text: str               # normalized, noise-stripped
    metadata: dict
    confidence: float       # 0–1, drives the "(est.)" labeling downstream
    fetched_at: datetime
```

`source_name` and `source_type` are exactly what render into the `[Source N — … — …]` header in Block 4. Keep the names aligned and the prompt envelope writes itself.

**Build order by coverage** (from the reverse index in `Final_Agents…docx`) — this is the correct build order, it is not arbitrary:

```
Firecrawl   14 agents  ─┐
Exa         12 agents   │  build these two and 18 of 24 agents can run
Google Docs  9 agents   │
LinkedIn     8 agents   │
Reddit       8 agents   │
Apollo       7 agents  ─┘
GCal 7 · Gmail 5 · SerpAPI 5 · Semrush 5 · X 5 · GA4 4 · GSC 4 · Ahrefs 4 …
```

**Graceful degradation is mandatory.** `agent.research.required` vs `.optional`. If an optional connector is missing or unauthorized, the run proceeds and the report says `Data not available` in that cell — per the STRICT rules. If a *required* connector fails, fail the run with a specific message. A missing Ahrefs key must never 500 an SEO audit.

---

## 9. Validation gate

The STRICT OUTPUT RULES in `Master_Prompt.docx` are currently instructions the model may ignore. Make them code.

```
generate → VALIDATE ──pass──► persist
              │
            fail
              │
              ▼
        targeted repair: re-prompt ONLY the broken part
        (max 1 attempt) → re-validate → persist or flag
```

Checks:

| Check | Rule |
|---|---|
| Sections | Every `agent.outline[].required` heading present, in order |
| Visuals | Every `agent.requiredVisuals` present and schema-valid |
| Chart schema | `type` present + allowed; pie sums 100; radar keys complete |
| Forbidden phrases | `Certainly`, `Sure!`, `Here is`, `Hope this helps`, `In conclusion`, `chunk`, `raw JSON`, `scrapped data`, `knowledge base`, `Tavily`, `Instagram scraper` |
| Placeholder links | No `imgur.com`, no `(Note: Replace with…)`, no `example.com` images |
| Preamble/postamble | First non-empty line must be the `#` title; last must be the terminal section |

**Repair, do not regenerate.** If section 5's pie chart is malformed, re-prompt for section 5's chart alone. A full regenerate costs full tokens and usually breaks something else.

---

## 10. Cost model

Three levers, in order of impact:

1. **Evidence cache (L4).** A brand's six agent runs share one crawl. Biggest single saving.
2. **Prompt caching on Blocks 1 + 3.** Keep them byte-stable and ordered first.
3. **Model tiering per agent.** `Legal Agreement Drafter` and `Content Calendar` do not need the same model as `Market Sizing & Entry`. Put `model.primary` in the agent config, not in the pipeline.

Instrument `cost_usd` per run from day one and surface it in an internal dashboard. You cannot price this product without it.

---

## 11. What I'd build, in order

| Phase | Deliverable | Unblocks |
|---|---|---|
| 0 | Repo recon → `docs/ARCH_CURRENT.md` | Everything else is written against reality |
| 1 | Agent catalog as data: types, registry, 24 configs, validator script | Removes the 24-code-paths risk permanently |
| 2 | Prisma schema + migrations + evidence cache | L4 |
| 3 | Connector interface; `web_scrapper`/`social_scrapper` refactored behind it | L3 |
| 4 | Prompt composer (4 blocks) + token budgeter + golden tests | L5 |
| 5 | Run orchestrator, job queue, SSE stage stream | L6 |
| 6 | Output validator + repair pass | L7 |
| 7 | Schema-driven question form (ONE component, all 24 agents) | L2 |
| 8 | Streaming run view + standardized recharts renderer | L8 |
| 9 | Report persistence, versioning, export profiles | L9 |
| 10 | **Proof:** add agent #25 in under 15 minutes, config only | Validates the whole thesis |

Phases 1 and 4 are the load-bearing ones. If those two are right, the rest is ordinary engineering.

---

## 12. Open decisions & contradictions found in the docs

These need a call before Phase 1 locks:

1. **Chart format — three competing specs.** Recommendation in §6: single ` ```recharts ` format, pill derived from `type`, Tab 4's ASCII style demoted to an export render profile.

2. **Agent count is 23 or 24.** `AGENTS_and_CATEGORIES.docx` numbers 23 agents, but Tab 13 adds a standalone **SEO Strategy** agent separate from **SEO Audit**. They have genuinely different questions and outputs — keep both, count is 24. Confirm.

3. **Generic connector labels block the build order.** Nine agents reference `CRM`, `Analytics`, `Search connectors`, `Social connectors` instead of a named provider (GTM Strategy, Product Launch, Festival, Seasonal, Revenue Model, Brand Personality, Campaign Structure, Sales Pitch, Cold Calling). The doc itself flags this as an action item. Resolve to concrete providers before Phase 3 or the dependency graph is fiction.

4. **`8JM` connector is unverified** (listed for Business Plan Generator). Likely a typo. Drop or identify.

5. **Two prompt philosophies.** Tab 3 is variable-driven and lean (`{user_brand_name}`, `{competitor_list}`); Tab 4 is maximalist and dense with hard section counts. Tab 3's variable approach is the right base for the config-driven architecture; Tab 4's *density requirements* (4–7 evidence-based points per quadrant, 6–8 prioritized recommendations) should be lifted into `agent.outline[].constraints` so the validator can enforce them.

6. **Gumloop-style agent descriptions are not system prompts.** The "I want you to help me set up the following agent…" text in two of the docs is Gumloop's *onboarding* copy, not a prompt. Use it as the agent's marketing blurb on the catalog card; write real system prompts from the Tab 3 template.

7. **Personal-data agents need a scope decision.** Recruiting Sourcer, Inbox Manager, Meeting Notes read user mailboxes and candidate data. They imply an OAuth + data-retention posture the strategy agents don't. Consider deferring the whole Productivity/Support cluster to v2 and shipping the 24 strategy agents first.

---

## 13. The thing most likely to go wrong

Not the LLM. **The research layer.** Instagram scraping breaks constantly, Firecrawl rate-limits, Ahrefs is expensive per call, and competitor sites block crawlers. The report quality is bounded entirely by evidence quality.

Budget real engineering for: per-connector retry with backoff, circuit breakers, a `TOOL_STATUS` health endpoint (you already have `TOOL_STATUS_AND_BENCHMARKING.md` — wire it to live checks), and a visible "evidence quality" score on each report so a thin-data run is honest about it rather than confidently generic.
