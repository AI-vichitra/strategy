# StratAI — Agent Registry Seed

Every agent from the docs, normalized into implementable config. Feed this file to Claude Code in Phase 1 and it can generate all 24 config files directly.

**Source reconciliation:** question option lists come from `AGENTS_and_CATEGORIES.docx` Tab 13 (the final, most specific version). Rationale (`why`) comes from the Tier 1–6 sections of the same doc. Connectors come from the per-category tables in Tab 13 plus the reverse index in `Final_Agents_Prompts_Categories.docx` Tab 2.

---

## 1. The config shape

```ts
// frontend/src/lib/agents/types.ts  (mirror in backend/app/agents/types.py)

export type QuestionType = 'single' | 'multi' | 'text';

export interface AgentQuestion {
  id: string;                 // stable; becomes the label in BRAND_CONTEXT
  label: string;              // shown to user
  type: QuestionType;
  options?: string[];         // required for single | multi
  maxSelect?: number;         // multi only
  placeholder?: string;       // text only
  required: boolean;
  why: string;                // internal — why this question earns its place
  gate?: boolean;             // if answered negatively, skip/disable the agent
}

export interface AgentVisual {
  id: string;
  chartType: 'bar' | 'line' | 'area' | 'radar' | 'pie';
  title: string;
  requirement: string;        // what the chart must contain — goes into the prompt
}

export interface AgentSection {
  id: string;
  heading: string;            // validator matches this literally
  required: boolean;
  constraints?: string;       // e.g. "4-7 evidence-based points"
  visualId?: string;
}

export interface AgentConfig {
  id: string;
  category: CategoryId;
  name: string;
  blurb: string;              // catalog card copy
  tier: 1 | 2 | 3 | 4 | 5 | 6;
  businessValue: 'high' | 'medium-high' | 'medium';
  complexity: 'low' | 'medium' | 'high';

  persona: {
    role: string;             // "Senior Competitive Intelligence Strategist"
    seniority: string;        // "15+ years advising CMOs and founders"
    objective: string;
  };

  questions: AgentQuestion[];           // 2-4, hard cap
  research: {
    required: ConnectorRef[];
    optional: ConnectorRef[];
    depth: 'standard' | 'deep';
  };
  frameworks: string[];                 // hints injected into AGENT_ROLE
  outline: AgentSection[];
  visuals: AgentVisual[];
  outputProfile: 'board-report' | 'audit' | 'calendar' | 'document';
  model: { primary: string; fallback: string; maxOutputTokens: number };
}
```

**Hard rules the registry validator must enforce:**
- `questions.length >= 2 && <= 4`
- every `single`/`multi` question has `options.length >= 2`
- every `visuals[].id` is referenced by exactly one `outline[].visualId`
- `id` is unique and kebab-case
- `research.required.length >= 1`

---

## 2. Categories

| id | Label | Agents |
|---|---|---|
| `digital-strategy` | Digital Strategy | 9 |
| `brand-strategy` | Brand Strategy | 3 |
| `performance-marketing` | Performance Marketing | 3 |
| `strategy-planning` | Strategy & Planning | 7 |
| `competitive-intelligence` | Competitive Intelligence | 1 |
| `legal-ops` | Legal & Ops | 1 |

---

## 3. Worked example — full config for one agent

Use this as the template Claude Code copies for the other 23.

```ts
// frontend/src/lib/agents/configs/seo-audit.ts
import type { AgentConfig } from '../types';

export const seoAudit: AgentConfig = {
  id: 'seo-audit',
  category: 'digital-strategy',
  name: 'SEO Audit Agent',
  blurb: 'Crawls your site, finds what is broken, and ranks the fixes by revenue impact — not by severity label.',
  tier: 1,
  businessValue: 'high',
  complexity: 'medium',

  persona: {
    role: 'Senior Technical SEO Consultant',
    seniority: '12+ years auditing sites for e-commerce, SaaS and local businesses',
    objective:
      'Produce a prioritized audit that a team can action this quarter. Rank every finding by its effect on the stated business goal, never alphabetically or by generic severity.',
  },

  questions: [
    {
      id: 'primary_goal',
      label: 'What is your primary SEO goal?',
      type: 'single',
      options: [
        'More Organic Traffic', 'More Leads', 'More Sales',
        'Better Local Rankings', 'Brand Visibility', 'Unsure',
      ],
      required: true,
      why: 'Shifts the audit from a general health check to targeted opportunity identification. A lead-gen audit and a traffic audit prioritize completely different fixes.',
    },
    {
      id: 'main_concern',
      label: 'Which issue concerns you the most?',
      type: 'single',
      options: [
        'Low Rankings', 'Low Traffic', 'Technical SEO',
        'Content Quality', 'Backlinks / Authority', 'Local SEO', 'Unsure',
      ],
      required: true,
      why: 'Allows prioritization. Without it the agent returns a 50-page audit of every issue found.',
    },
    {
      id: 'priority_keywords',
      label: 'Which keywords matter most to your business?',
      type: 'text',
      placeholder: 'e.g. AI Marketing, CRM Software, Luxury Apartments Gurgaon',
      required: false,
      why: 'Single highest-value SEO input. Ensures recommendations target revenue-driving keywords rather than vanity metrics.',
    },
  ],

  research: {
    required: [{ provider: 'firecrawl', kind: 'site_crawl' }],
    optional: [
      { provider: 'gsc', kind: 'performance' },
      { provider: 'ahrefs', kind: 'backlinks' },
      { provider: 'semrush', kind: 'keywords' },
      { provider: 'bing_webmaster', kind: 'performance' },
    ],
    depth: 'deep',
  },

  frameworks: ['technical-seo-pillars', 'eeat', 'search-intent-mapping'],

  outline: [
    { id: 'exec', heading: 'Executive Summary', required: true,
      constraints: '6-10 sentences. Lead with the single highest-impact finding.' },
    { id: 'health', heading: 'Site Health Scorecard', required: true,
      visualId: 'health_radar' },
    { id: 'technical', heading: 'Technical Findings', required: true,
      constraints: 'Table: Issue | Pages Affected | Impact | Effort | Priority' },
    { id: 'content', heading: 'Content & Intent Gaps', required: true,
      constraints: '4-7 evidence-based points, each citing a crawled URL' },
    { id: 'authority', heading: 'Authority & Backlink Signal', required: true,
      visualId: 'authority_bar' },
    { id: 'priority', heading: 'Prioritized Fix List', required: true,
      constraints: 'Exactly 10 rows, ranked by impact on the stated primary goal' },
    { id: 'measure', heading: 'What to Measure in 30-60 Days', required: true,
      constraints: 'One metric, one target, one checkpoint date' },
  ],

  visuals: [
    { id: 'health_radar', chartType: 'radar',
      title: 'Site Health by Pillar (1-10)',
      requirement: 'Axes: Crawlability, Indexation, Page Speed, On-Page, Content Depth, Authority. Score from crawl evidence only.' },
    { id: 'authority_bar', chartType: 'bar',
      title: 'Authority Signal vs Category Benchmark',
      requirement: 'Client brand plus up to 4 competitors. Label estimates with (est.).' },
  ],

  outputProfile: 'audit',
  model: { primary: 'claude-opus-4', fallback: 'claude-sonnet-4', maxOutputTokens: 16000 },
};
```

---

## 4. All 24 agents — question schemas

`S` = single select · `M` = multi select · `T` = text · `[G]` = gate question

### DIGITAL STRATEGY

**`seo-strategy` — SEO Strategy Agent** · T1 · value: high · complexity: medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What is your primary SEO objective? | S | More Organic Traffic · More Leads · More Sales · Local SEO Growth · Brand Visibility · Thought Leadership |
| 2 | What is your biggest SEO challenge? | S | Low Rankings · Low Traffic · Lack of Content · Technical SEO Issues · Backlinks / Authority · Local Visibility · Unsure |
| 3 | Which keywords matter most to your business? | T | — |

Connectors: **req** firecrawl · **opt** gsc, ahrefs, semrush, serpapi

---

**`seo-audit` — SEO Audit Agent** · T1 · high · medium — *full config in §3*

---

**`geo-aeo` — GEO/AEO Agent** · T1 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which AI visibility channel matters most? | S | ChatGPT · Google AI Overviews · Perplexity · Gemini · Claude · All AI Platforms |
| 2 | What is your primary GEO/AEO objective? | S | Increase Brand Visibility · Generate Leads · Increase Website Traffic · Become an Industry Authority · Improve AI Citations · Improve Local Visibility |
| 3 | What best describes your current AI visibility? | S | No Visibility · Rarely Mentioned · Occasionally Mentioned · Frequently Mentioned · Unsure |

> Tier-1 notes add a fourth high-value question worth keeping: **"Are you in a YMYL industry?"** (Yes/No) — it flips the whole strategy to E-E-A-T-first. Recommend adding as Q4.

Connectors: **req** firecrawl, serpapi · **opt** gsc, ahrefs, semrush, bing_webmaster
Frameworks: `eeat`, `citation-worthiness`, `entity-optimization`

---

**`topical-strategy` — Topical Strategy Agent** · T1 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What is the primary topic you want to build authority around? | T | e.g. AI Marketing · Real Estate Investment · Diabetes Care · Cybersecurity |
| 2 | What is the primary objective? | S | SEO Rankings · GEO / AI Visibility · Lead Generation · Thought Leadership · Brand Awareness |
| 3 | What is your current content maturity? | S | No Existing Content · Some Content · Large Content Library · Industry Authority |

Connectors: **req** exa, firecrawl · **opt** semrush, reddit
Frameworks: `pillar-cluster`, `hub-and-spoke`, `topical-authority-map`

---

**`trend-strategy` — Trend Strategy Agent** · T1 · medium · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which trend category matters most? | S | Industry Trends · Consumer Trends · Technology Trends · Social Media Trends · Market Trends · All Relevant Trends |
| 2 | What do you want to achieve from trends? | S | Content Ideas · Lead Generation · Thought Leadership · Product Innovation · Brand Awareness |
| 3 | How quickly can your team act on opportunities? | S | Same Day · Within a Week · Within a Month · Quarterly Planning |

Connectors: **req** reddit, exa · **opt** x, youtube, google_trends
> Q3 is the executability filter — it prevents recommending daily-reaction trends to a team on a quarterly cycle.

---

**`seasonal-strategy` — Seasonal Strategy Agent** · T1 · high (if applicable) · low
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Does your business experience seasonal demand? **[G]** | S | Yes · No · Not Sure |
| 2 | Which season matters most to your business? | S | Summer · Winter · Monsoon · Multiple Seasons |
| 3 | What is the primary goal of your seasonal campaigns? | S | Increase Sales · Generate Leads · Increase Footfall · Brand Awareness · Customer Retention |

Connectors: **req** firecrawl · **opt** ga4, gsc, serpapi
> Q1 is a true gate: answer "No" and the UI should recommend a different agent rather than generating a hollow report.

---

**`festival-strategy` — Festival Strategy Agent** · T1 · medium · low
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which festival or event do you want to build a campaign around? | S | Diwali · Christmas · New Year · Black Friday / Cyber Monday · Valentine's Day · Eid · Holi · Independence Day · Industry Event · Other |
| 2 | What is the primary objective of this campaign? | S | Sales · Lead Generation · Brand Awareness · Customer Engagement · Product Launch · Customer Retention |
| 3 | What type of offer are you willing to run? | S | Discounts · Bundles · Free Trial · Giveaway · Content-Led Campaign · No Offer (Brand Campaign) |

Connectors: **req** exa, serpapi · **opt** google_calendar, reddit, x
> The research brief calls this out as a flagship: *"a festive special agent which reads previous years' trends."* Prior-year retrieval should be a required research step, not optional.

---

**`social-media-strategy` — Social Media Strategy Agent** · T2 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which social platforms are your priority? | **M** | LinkedIn · Instagram · Facebook · X (Twitter) · YouTube · Reddit · Pinterest · Multiple Platforms |
| 2 | What is your primary social media goal? | S | Brand Awareness · Lead Generation · Sales · Community Building · Customer Engagement · Thought Leadership · Product Adoption · Customer Support |
| 3 | What is your biggest social media challenge? | S | Low Reach · Low Engagement · Low Followers · Low Leads · Low Conversions · Inconsistent Content · Lack of Content Ideas · Limited Resources · Unsure |

Connectors: **req** instagram, firecrawl · **opt** linkedin, x, reddit, youtube

---

**`content-calendar` — Content Calendar Agent** · T2 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which channels need content? | **M** | Blog · LinkedIn · Instagram · Facebook · X · YouTube · Email Newsletter · Multiple Channels |
| 2 | What is your primary content objective? | S | Brand Awareness · Lead Generation · Sales · SEO Growth · GEO / AI Visibility · Customer Education · Community Building · Thought Leadership |
| 3 | What content frequency can your team realistically maintain? | S | Daily · 3–5 Times Per Week · Weekly · Bi-Weekly · Monthly |

Connectors: **req** firecrawl · **opt** semrush, reddit, youtube, notion, google_docs
`outputProfile: 'calendar'` — this agent's primary artifact is a dated table, not a narrative report. Needs its own render profile and a `.ics` / CSV export.

---

### BRAND STRATEGY

**`brand-audit` — Brand Audit Agent** · T2 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What aspect of your brand concerns you most? | S | Brand Awareness · Brand Perception · Messaging Clarity · Visual Identity · Differentiation · Trust & Credibility · Consistency Across Channels · Other |
| 2 | Who is your primary target customer? | S | *(see shared `TARGET_CUSTOMER` option set below)* |
| 3 | Which outcome are you hoping to improve? | S | More Leads · More Sales · Stronger Brand Recognition · Better Market Positioning · Higher Trust · Better Customer Retention |

Connectors: **req** firecrawl · **opt** gsc, ga4, reddit, x, instagram

---

**`brand-positioning` — Brand Positioning Agent** · T2 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What problem does your business solve? | T | Be specific — not "make life better" |
| 2 | Who are your 2–3 main competitors? | T | Names or URLs |
| 3 | What is your unfair advantage? | S | Tech · Team · Process · Data · Community · Speed · Cost · Other |

Connectors: **req** firecrawl, exa · **opt** serpapi
Frameworks: `brand-pyramid`, `brand-key`, `category-entry-points`, `positioning-map`

---

**`brand-personality` — Brand Personality & Guidelines Agent** · T2 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | How do you want your brand to be perceived? *(up to 3)* | **M** max 3 | Professional · Innovative · Premium · Friendly · Authoritative · Playful · Luxury · Trustworthy · Bold · Approachable |
| 2 | Who is your primary target customer? | S | *(shared `TARGET_CUSTOMER`)* |
| 3 | Which brands do you admire from a communication perspective? | T | e.g. Apple, Nike, HubSpot, Tesla, Airbnb |

Connectors: **req** firecrawl · **opt** instagram, linkedin, x
Frameworks: `jungian-archetypes`, `tone-of-voice-matrix`
> Q3 is calibration, not flattery — it anchors the output to a reference voice. The research doc's "Brand Kit" concept (logo, fonts, colours, tone, emotion, character, syntax) is this agent's natural output shape.

---

### PERFORMANCE MARKETING

**`campaign-structure-architect` — Campaign Structure Architect** · T2 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which advertising platform are you using? | **M** | Google Ads · Meta Ads · LinkedIn Ads · Microsoft Ads · Multiple Platforms · Other |
| 2 | What is your primary campaign objective? | **M** | Lead Generation · Sales · App Installs · Brand Awareness · Website Traffic · Product Launch · Other |
| 3 | What best describes your advertising maturity? | S | Never Run Ads · Beginner · Intermediate · Advanced · Enterprise Scale |

Connectors: **req** — · **opt** google_ads, ga4
> Tier-2 notes include a budget-band question (Micro <$5K · Small $5–25K · Medium $25–100K · Large $100K+). Worth adding as Q4 — it changes realistic channel mix materially.

---

**`bidding-budget-optimisation` — Bidding & Budget Optimisation Agent** · T3 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which advertising platforms are you actively using? | **M** | Google Ads · Meta Ads · LinkedIn Ads · Microsoft Ads · Multiple Platforms |
| 2 | What is your primary advertising objective? | **M** | Lead Generation · Sales · ROAS Improvement · Scale Spend · Lower CPA · Brand Awareness |
| 3 | What is your biggest performance challenge? | S | High CPA · Low ROAS · Low Conversion Rate · Limited Budget · Scaling Issues · Unstable Performance |

Connectors: **req** google_ads · **opt** ga4
> Flagged in the docs as *"needs account data"*. Without a live Google Ads connection this agent produces generic advice. Gate the catalog card on connector status: show it as "Connect Google Ads to enable".

---

**`attribution-measurement` — Attribution & Measurement Agent** · T3 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What marketing channels are you currently using? | **M** | Google Ads · Meta Ads · LinkedIn Ads · SEO · Email Marketing · Organic Social · Partnerships · Multiple Channels |
| 2 | What is your biggest measurement challenge? | S | Can't identify what drives conversions · Inaccurate attribution · Missing tracking · Reporting is fragmented · No dashboarding · Unsure |
| 3 | What decision do you want attribution to improve? | S | Budget Allocation · Campaign Optimization · Channel Performance · CAC Reduction · Revenue Attribution · Executive Reporting |

Connectors: **req** ga4 · **opt** gsc, google_ads, bigquery

---

### STRATEGY & PLANNING

**`gtm-strategy` — GTM Strategy Agent** · T4 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What is your primary GTM objective? | S | Launch a new product/service · Enter a new geographic market · Enter a new customer segment · Increase customer acquisition · Increase revenue from existing customers · Improve product adoption · Increase market share · Reposition the brand · Other |
| 2 | Who is your primary target customer? | S | *(shared `TARGET_CUSTOMER`)* |
| 3 | What is your biggest growth constraint today? *(up to 2)* | **M** max 2 | Limited marketing budget · Low brand awareness · Strong competition · Lack of qualified leads · Low conversion rates · Weak sales process · Long sales cycles · Product adoption challenges · Customer retention issues · Market education required · Limited internal resources · Other |
| 4 | What stage is your business currently in? **(critical)** | S | New business / Startup · Early growth · Scaling · Mature business · Market leader · Declining / Stagnant growth |

Connectors: **req** firecrawl, exa · **opt** instagram, serpapi, hubspot, salesforce, ga4
Frameworks: `13-element-gtm`, `ansoff-matrix`, `aarrr`, `gtm-motion`, `icp`

**Required visuals** — the master prompt mandates exactly five, all must appear:
| id | type | content |
|---|---|---|
| `segment_pie` | pie | Target customer segment breakdown, sums to 100 |
| `capability_radar` | radar | Brand Power · Price Flexibility · Digital Presence · Innovation · Distribution — user brand vs competitors, 1–10 |
| `growth_projection` | area | 90-day projection: Month 1, 2, 3, 6 |
| `channel_efficiency` | bar | Channel efficiency vs cost index, 1–10, filtered by the stated constraint |
| `execution_ramp` | bar | Execution intensity: Pre-Launch · Launch Week · Month 1 · Scaling |

**Outline** (from the master prompt, enforce verbatim): Executive Summary & Positioning Statement · Target Audience & ICP Profiles · GTM Comparative Matrix · Pricing & Packaging Strategy · 90-Day Actionable GTM Roadmap · Metrics & Risk Mitigation Plan. One takeaway sentence directly under every chart.

---

**`product-launch-strategy` — Product Launch Strategy Agent** · T4 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What are you launching? | S | New Product · New Service · New Feature · New Brand · New App / Software · Existing Product Relaunch · Other |
| 2 | What is the primary objective of this launch? | S | Generate Sales · Generate Leads · Build Awareness · Acquire Users · Drive Product Adoption · Enter a New Market · Validate Demand · Increase Word of Mouth · Other |
| 3 | What is your planned launch timeline? | S | Within 30 Days · 1–3 Months · 3–6 Months · 6–12 Months · Flexible |

Connectors: **req** firecrawl, exa · **opt** instagram, serpapi, hubspot
> Tier-4 notes add a strong Q4: **"Is your audience already aware of the problem you solve?"** (Yes, existing demand · No, education needed · Mix). This flips the strategy between demand *capture* and demand *creation*. Recommend adding.

---

**`market-sizing-entry` — Market Sizing & Entry Agent** · T4 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which market are you evaluating? | T | e.g. UAE · Saudi Arabia · US Healthcare · AI CRM Software · Luxury Real Estate India |
| 2 | What is your objective? | **M** | Launch a New Business · Launch a New Product · Enter a New Geography · Enter a New Customer Segment · Expansion Planning · Investment Evaluation |
| 3 | Do you have existing customer data in this market? | S | Yes · No · Partial |

Connectors: **req** exa, firecrawl, serpapi
Frameworks: `tam-sam-som`, `pestle`, `porters-five-forces`, `ansoff-matrix`

---

**`icp-personas` — ICP & Personas Agent** · T4 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Which customer group drives the most value today? | S | Consumers · Small Businesses · Mid-Market Companies · Enterprise Organizations · Government · Not Sure |
| 2 | What is your biggest customer acquisition challenge? | S | Wrong Leads · Low Conversion · Long Sales Cycle · Low Awareness · High CAC · Poor Retention · Not Sure |
| 3 | What is your primary growth objective? | S | More Leads · Higher Conversions · Larger Deals · Better Retention · Market Expansion · Product Adoption |

Connectors: **req** firecrawl · **opt** hubspot, salesforce, apollo
Frameworks: `icp`, `buyer-persona`, `jobs-to-be-done`, `meddic`
> Output shape from the MindPal persona prompt is worth keeping: 3 personas (demographics, background, goals, pain points, motivations, behaviours, needs) + key insights + 3 acquisition ideas + 3 CRO ideas + 3 content ideas.

---

**`partnership-distribution` — Partnership & Distribution Strategy Agent** · T4 · medium-high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What is your primary partnership objective? | S | Generate Revenue · Acquire Customers · Expand Distribution · Increase Brand Awareness · Enter New Markets · Access New Technology · Strategic Alliances |
| 2 | What type of business are you? | S | SaaS · E-commerce · Agency · Professional Services · Healthcare · Real Estate · Marketplace · Consumer Brand · Other |
| 3 | Which partnership model interests you most? | S | Referral Partners · Resellers · Affiliates · Strategic Alliances · Technology Integrations · Channel Partners · Other |

Connectors: **req** exa · **opt** linkedin, apollo
Frameworks: `build-partner-buy`, `channel-strategy`, `business-model-canvas`

---

**`revenue-model-strategy` — Revenue Model Strategy Agent** · T4 · high · **high**
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What best describes your current revenue model? | S | Subscription (SaaS) · One-Time Purchase · Services · Marketplace · Advertising · Licensing · Multiple Revenue Streams · Pre-Revenue |
| 2 | What is your primary monetization goal? | **M** | Increase Revenue · Improve Profitability · Introduce New Revenue Streams · Improve Pricing · Increase Customer Lifetime Value · Reduce Customer Churn |
| 3 | What is your biggest revenue challenge? | S | Pricing · Customer Acquisition Cost · Low Retention · Low Conversion · Limited Revenue Streams · Weak Upsells · Unsure |

Connectors: **req** firecrawl · **opt** hubspot, salesforce, ga4
Frameworks: `business-model-canvas`, `value-proposition-canvas`, `pricing-ladder`

---

**`business-plan-generator` — Business Plan Generator Agent** · T4 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What stage is the business currently in? | S | Business Idea · MVP / Prototype · Early Revenue · Growing Business · Established Business · Pivoting Existing Business |
| 2 | What is the primary purpose of this business plan? | **M** | Start the Business · Raise Funding · Internal Planning · Bank Loan · Expansion Strategy · Investor Pitch |
| 3 | What is your business model? | S | SaaS · E-commerce · Marketplace · Agency · Professional Services · Healthcare · Real Estate · Mobile App · Manufacturing · Other |

Connectors: **req** exa · **opt** firecrawl, serpapi, google_docs
`outputProfile: 'document'` — sections Product · Marketing · Sales · Finance · Hiring · Competition · Funding. The source prompt asks for Excel-transferable structure; implement as a multi-sheet XLSX export alongside the report.
> Connector `8JM` listed in the source doc is unverified — drop it.

---

### COMPETITIVE INTELLIGENCE

**`competition-analysis` — Competition Analysis Agent** · T5 · high · medium
| # | Q | Type | Options |
|---|---|---|---|
| 1 | Who are your 2–3 main competitors? | T | Names or URLs. If unknown, this agent is premature. |
| 2 | What aspect of competition matters most? | S | Messaging · Pricing · Features · Customer Experience · Go-to-Market · All |
| 3 | What decision will this analysis inform? | S | Positioning · Product Features · Pricing · GTM · Differentiation |

Connectors: **req** firecrawl, exa · **opt** instagram, serpapi, ahrefs, reddit
Frameworks: `swot-tows`, `positioning-map`, `porters-five-forces`, `share-of-voice`

**Required visuals** (from the master prompt):
| id | type | content |
|---|---|---|
| `revenue_scale_bar` | bar | Revenue & distribution scale, every brand, same currency unit stated |
| `pricing_radar` | radar | Affordability · Premium Positioning · Value For Money · Innovation Premium — client + top 3 overlapping competitors only, for legibility |
| `sov_pie` | pie | Social media share of voice, sums to 100, remainder bucketed as "Others" |

**Outline** (enforce verbatim): Competitive Landscape Overview · Market Share & Scale Comparison · Competitive Benchmarking Table · SWOT Analysis · Share of Voice Analysis · Strategic Recommendations (Short/Medium/Long-Term, 3 each) · Risk Mitigation Plan · `**End of Report**`.

Benchmarking table caps at the 4 most relevant competitors with a footnote naming exclusions. SWOT: client gets two side-by-side tables (4 bullets per quadrant); each competitor gets one packed 3–4 sentence inline paragraph.

---

### LEGAL & OPS

**`legal-agreement-drafter` — Legal Agreement Drafter Agent** · T6 · medium · low
| # | Q | Type | Options |
|---|---|---|---|
| 1 | What type of agreement do you need? **[G]** | **M** | NDA · Service Agreement · Partnership Agreement · Employment Agreement · Vendor Agreement · Contractor Agreement · Other |
| 2 | Which party are you? | S | Service Provider · Client · Employer · Employee · Business Partner · Vendor |
| 3 | What jurisdiction should this agreement follow? | S | India · United States · United Kingdom · UAE · Australia · Other |

Connectors: none — this agent is prompt-only.
`outputProfile: 'document'`
> Ship with a standing non-advice disclaimer block and a mandatory "have counsel review" line. Q1 is a hard gate: agreement types are structurally different documents, not variations.

---

## 5. Shared option sets

Define once, reference by name — three agents use `TARGET_CUSTOMER` and they must stay identical.

```ts
export const TARGET_CUSTOMER = [
  // B2C
  'Consumers (Mass Market)',
  'Affluent / Premium Consumers',
  'Gen Z',
  'Millennials',
  'Parents & Families',
  // B2B
  'Small Businesses (1–50 employees)',
  'Mid-Market Companies (51–1000 employees)',
  'Enterprise Organizations (1000+ employees)',
  'Government / Public Sector',
  // Mixed
  'B2B and B2C',
  'Other',
];
```

Used by: `gtm-strategy` Q2 · `brand-audit` Q2 · `brand-personality` Q2.

---

## 6. Connector dependency summary

Build in this order — the first two unlock 18 of 24 agents.

| Connector | Agents | Required by | Priority |
|---|---|---|---|
| **firecrawl** | 14 | seo-strategy, seo-audit, geo-aeo, topical, seasonal, social-media, content-calendar, brand-audit, brand-positioning, brand-personality, gtm, product-launch, market-sizing, icp, revenue-model, competition-analysis | **P0** |
| **exa** | 12 | topical, festival, brand-positioning, gtm, product-launch, market-sizing, partnership, business-plan, competition-analysis | **P0** |
| **instagram** | 5 | social-media-strategy | **P0** — already built in `social_scrapper/` |
| serpapi | 5 | geo-aeo, festival, market-sizing | P1 |
| semrush | 5 | — | P1 |
| gsc | 4 | — | P1 |
| ahrefs | 4 | — | P1 |
| ga4 | 4 | attribution-measurement | P1 |
| reddit | 8 | trend-strategy | P1 |
| google_ads | 3 | bidding-budget | P2 |
| linkedin | 8 | — | P2 |
| hubspot / salesforce | 4 | — | P2 |
| bigquery, notion, google_docs, x, youtube, apollo, bing_webmaster, google_trends | — | — | P3 |

**Unresolved generic references to fix before Phase 3** — these agents reference `CRM` / `Analytics` / `Search connectors` / `Social connectors` instead of a named provider:
`gtm-strategy`, `product-launch-strategy`, `festival-strategy`, `seasonal-strategy`, `revenue-model-strategy`, `brand-personality`, `campaign-structure-architect`. The mappings proposed above are my resolution — confirm or override before locking.

---

## 7. Agents deliberately deferred to v2

The docs also catalog Sales & Outreach, Data & Analytics, Productivity & Ops, Research & Intelligence, and Support & Success clusters (Meeting Prep, CRM Pipeline Reporter, Lead Enrichment, Inbox Manager, Recruiting Sourcer, Support Inbox, Issue Tracker…).

These are a **different product**: they read live mailboxes, CRMs, ticket queues and candidate data. They need OAuth scopes, write permissions, data-retention policy and a per-user (not per-brand) data model. The 24 strategy agents above need none of that.

Ship the strategy tool first. The infrastructure built for it — agent-as-data registry, connector interface, prompt composer, validator — carries over to the ops agents unchanged when you do build them.

One note on their prompt text: the `"I want you to help me set up the following agent…"` bodies in the docs are **Gumloop's onboarding copy**, not system prompts. Use them as catalog-card blurbs; write the real system prompts from the Tab 3 template.
