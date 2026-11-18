# Session Review — Cross-Feature Seams

Read-only review of how this session's four features compose together. Per-feature
behavior was already verified by the implementing forks; this pass only checks the
seams *between* them, by reading the current code directly.

Features in scope:
1. Reference-doc upload → brand KB
2. Logo-palette auto-fill (shared `BrandKitForm`)
3. Hybrid competitor discovery engine (backend)
4. Industry/Region + trust-signal confirm UI (frontend)

---

## Findings (ranked by severity)

### 1. [MEDIUM] Hybrid engine's "legitimately zero competitors" case is indistinguishable from a hard failure, so it silently falls back to the ungrounded legacy path

`backend/services/competitor_service.py:313-323`:

```python
raw = tavily_comp.search_candidates(...)
...
raw_results = raw.get("results") if isinstance(raw, dict) else None
if not raw_results:
    return None
```

`resolve_competitors` (same file, lines 139-140) is explicitly designed so that an
empty raw-results list produces a valid `[]` ("LLM legitimately finds zero genuine
competitors... that is a successful result, not a fallback" — see the function's own
docstring at lines 126-130). But `discover_and_resolve` never reaches that branch: if
Tavily's structured search (after the new directory-domain denylist) returns zero
hits — which is a real, observed outcome; the implementing fork hit exactly this case
twice during its own verification (Amul, Swiggy) before widening the query set — it
returns `None` at line 323, and `tavily_service.search_competitors` (line 88,
`if enriched is not None`) treats that identically to an API failure: it silently
falls back to `tavily_comp.get_competitors()`, the old regex-on-`answer` heuristic
with no grounding and no verification.

Net effect: for a brand where the hybrid engine would correctly and confidently
report "no genuine competitors found" (a trustworthy empty result), the user instead
gets whatever the untrusted legacy heuristic happens to regex out of free text —
exactly the un-auditable result this whole feature exists to replace, and silently so
(no `tavily_error`, no signal to the frontend that the fallback occurred).

**Fix direction:** have `discover_and_resolve` distinguish "the Tavily call itself
failed/raised" (→ `None`, fall back) from "the call succeeded with 0 results" (→
proceed into `resolve_competitors([])`, which already correctly returns `[]`). Only
the former should trigger the legacy fallback.

### 2. [MEDIUM-HIGH] `backend/stratai.db` is a committed SQLite file acting as the de-facto prod database, and this session's schema change lives only in the uncommitted working copy

`git ls-files` confirms `backend/stratai.db` is tracked, and `git status` shows it
`M`odified but **not yet committed**. No `Base.metadata.create_all()` call exists
anywhere in the current runtime code (confirmed by grep across `backend/*.py`) — the
only references are inside `backend/alembic/versions/*.py` docstrings describing how
*prior* ad-hoc tables were created, by hand, once. Combined with Alembic being parked
(no working `env.py`/`alembic.ini` URL), this means the committed `stratai.db` file
*is* the schema-of-record: there is no code path that will add a missing column to an
existing deployed database on its own.

This session added `BrandConfig.reference_docs` (`backend/models/brand.py:23`) and a
one-off script, `backend/scripts/add_reference_docs.py`, which was run against the
local `stratai.db` as part of verification — but if the code changes get
committed/deployed without either (a) committing the now-modified `stratai.db` binary
alongside them, or (b) re-running `add_reference_docs.py` against whatever database
is actually deployed, the first read/write touching `reference_docs` (brand confirm
at `backend/routers/brand.py:156`, or the pipeline's KB-compile step at
`backend/services/pipeline_service.py:552-568`) will raise
`sqlite3.OperationalError: no such column: reference_docs` — a genuine 500.

This is not a new category of risk — `add_brand_kit.py`, `add_competitor_details.py`,
and `add_extracted_palette.py` show the exact same pattern already existed for prior
columns — but it is live and unresolved for *this* session's column specifically
right now, so flagging it before it's forgotten.

**Fix direction:** either commit the modified `backend/stratai.db`, or make running
one-off migration scripts an explicit, enforced step of this project's deploy
process (the parked Alembic work would be the real fix).

### 3. [LOW] Reference-doc `ref_id`s carry no ownership check — any authenticated user who supplies a valid `ref_id` gets its content folded into their own brand's context

`backend/services/reference_service.py:109-119` (`load_reference_text`) and
`_resolve_ref_path` (lines 24-34) validate only that `ref_id` doesn't escape the
uploads directory (path-traversal guard) — there is no check anywhere that the
`ref_id` being read actually belongs to the requesting user. This is consumed from
two call sites, neither of which adds an ownership check:
- `backend/routers/brand.py:147,156` (`confirm_brand`) — serializes whatever
  `reference_docs` list the client sends, verbatim, onto `BrandConfig.reference_docs`.
- `backend/services/competitor_service.py:59-79` (`_build_brand_context`) — loads
  text for whatever `reference_ref_ids` the client sends in `BrandSearchRequest`,
  folds it into the LLM resolver's prompt.

In practice this requires guessing a 128-bit `uuid.uuid4().hex` (`reference_service.py:86`),
so it is not realistically exploitable by blind brute force. It becomes relevant only
if a `ref_id` ever leaks elsewhere (shared team logs, a referrer header, a support
ticket) — at which point another user's uploaded document content could be folded
into a different brand's KB or competitor-discovery prompt with no ownership
re-check at consumption time.

**Fix direction:** either tie `ref_id` lookups to the uploading `user_id` (would need
a DB row per reference doc instead of loose files), or accept this as intentional
given the unguessable-id model and document it as such.

---

## Clean seams (explicitly checked, no issue found)

**`reference_ref_ids` consistency (feature 4 ↔ feature 1).** Both the
`search-competitors` POST body (`frontend/src/app/brand-setup/page.tsx:158`,
`reference_ref_ids: referenceDocs.map(d => d.ref_id)`) and the `confirm` POST body
(`page.tsx:224`, `reference_docs: referenceDocs.length > 0 ? referenceDocs : null`)
read from the exact same `referenceDocs` React state (`page.tsx:64`). `ReferenceUpload`
only renders during the `'form'` step (`page.tsx:401`), so the set of uploaded docs
cannot change between the `search-competitors` call and the final `confirm` call
unless the user clicks "Back" to the form step and re-submits — in which case both
calls simply use the updated set together, consistently. **No divergence found.**

**`BrandKitForm` shared-component correctness (feature 2).** The palette-autofill
logic lives entirely inside the shared component
(`frontend/src/components/BrandKitForm.tsx:115-132`) and checks emptiness against
live `colorDrafts` state, not the parent's `brandKit` prop, so a user-typed hex is
never overwritten regardless of which parent renders the form. Both call sites —
wizard (`frontend/src/app/brand-setup/page.tsx:396`) and chat
(`frontend/src/components/builder/MainContent.tsx:1829`) — pass identical props and
use an identical `hasBrandKit` persistence guard
(`page.tsx:220-223` / `MainContent.tsx:1185-1187`). Neither caller needed any
change for this feature to work on both paths. **No issue found.**

**`search_competitors` flag-OFF path (feature 3).** `git diff` against the
pre-session version of `backend/services/tavily_service.py` confirms the legacy
branch (`if not used_llm_resolver:` at line 102) calls
`tavily_comp.get_competitors()` with a function body that is byte-for-byte untouched
in `web_scrapper/tavily_comp.py` (confirmed via diff — only new code was *added*
after it). `_append_user_competitors` (lines 133-148) never caps or drops a
user-provided entry — it only skips an entry whose name case-insensitively matches
one already present.

One caveat worth being precise about: the merge is **not** byte-identical in every
case, by design. Previously the cap (`candidates[:8]`) was applied *after* merging
user competitors, so a full 8-item auto-discovered list could push user entries past
the slice and drop them — this was the bug the session's spec explicitly asked to
fix. The fix (`tavily_service.py:123-124`, cap applied only to the auto-discovered
list *before* appending user entries) changes output in exactly that
previously-buggy scenario, for both flag states, intentionally. Outside that
scenario, output is identical to pre-session behavior.

**Enriched competitor shape, backend → router → confirm UI (features 3 + 4).** The
`{name, website_url, source_url, summary, verified}` shape
(`backend/services/competitor_service.py:223-228`) flows through
`tavily_service.search_competitors` (`tavily_service.py:90-100`, additive keys
alongside the always-present legacy keys) → the router response
(`backend/routers/brand.py`, returned as-is) → the frontend's response mapping
(`page.tsx:173-182`, each enriched field read with `||`/`typeof` guards and falling
through to `undefined` when absent) → conditional rendering (`page.tsx:531-581`,
badge/summary/source-link each gated on the field's presence). Traced the legacy bare
`{name, url}` shape through the same code: every enriched-field read on such an
object evaluates to `undefined`, every conditional guard (`typeof cand.verified ===
'boolean'`, `cand.summary &&`, `cand.source_url &&`) evaluates to `false`, and
`website_url: c.website_url || c.url || ''` correctly falls back to the legacy `url`
key. **No issue found; degrades correctly in both directions.**

**Secrets.** Checked every new/changed file that handles a key or uploaded content:
`backend/services/competitor_service.py`, `backend/services/reference_service.py`,
`backend/routers/brand.py`, `backend/routers/projects.py`,
`backend/services/brand_theme.py`'s new `extract_palette_from_logo`. None log an API
key, a Firecrawl/reference-doc content body, or any `.env` value — warnings log only
URLs, filenames, or exception messages. `firecrawl_service.scrape_url` (pre-existing,
called by the new `verify_competitors`) sends the key via an `Authorization` header,
not a URL, so it can't leak into an exception's string representation either.

**Error/empty composition (no LLM key + no Firecrawl key + empty discovery,
together).** Traced the combination: if the resolver is enabled but Tavily's
structured search returns nothing, `discover_and_resolve` returns `None` before ever
checking for an LLM key (see Finding 1 — this is itself the finding, but it does not
*crash*). If results exist but no LLM key is configured, `resolve_competitors` catches
`RuntimeError` from `_get_llm_provider()` and returns `None` cleanly (line 136-137).
If an LLM key exists but no Firecrawl key, `verify_competitors` returns every item
with `verified: False` and drops nothing (lines 262-263). All three absent
simultaneously degrades to the plain legacy path with no exception raised anywhere
in the chain. **No crash found in any combination.**

---

## Questions for Moody

1. Is it intentional that a brand with zero *genuine* auto-discoverable competitors
   (Finding 1) should fall back to the old heuristic instead of trusting the hybrid
   engine's own empty result? If not, that's a one-line fix.
2. Is `backend/stratai.db` actually how this app ships to any real environment today
   (vs. a separate prod database this repo doesn't contain), or is dev-only and
   Finding 2 is moot for the real deployment path? I couldn't determine the
   deployment story from the code alone.
3. Is the unguessable-UUID model (Finding 3) an accepted trust boundary already, or
   worth tightening given reference docs can carry a brand's internal/confidential
   content?
