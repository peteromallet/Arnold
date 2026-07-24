# AR3: Media cost model — neutral `media_usage` record + per-media-unit pricing

**Milestone id:** `AR3-media-cost-model` · **Profile:** `premium` · **Robustness:** `thorough` · **Depth:** `high` · **Vendor:** `codex`

**OPTIONAL milestone.** AR3 is explicitly optional: if descoped, media cost stays opaque-but-documented (`CostStatus="unknown"`, budgets still apply) — the brief states the limitation either way. It is additive and depends on no other AR milestone except that the AR1 non-model adapter is the source of the `MediaUsage` record (the emission path).

Covers the cost/usage half of ticket area **E**. Runs on `arnold-generalized-pipeline` after
C1–C4 land. Cost accounting today is TOKEN-ONLY: `CanonicalUsage`
(`arnold/pipelines/megaplan/agent/agent/usage_pricing.py:28`) has `input_tokens` / `output_tokens`
/ cache / reasoning tokens and nothing else, and the pricing rows are per-million-tokens. That type
lives ONLY in the megaplan-coupled module — the generic `arnold/agent/agent/usage_pricing.py` is a
shim that re-imports it, so there is NO neutral usage type to extend. C2 added media *budgets*
(frame/resolution/seconds/size caps) but media *cost* is unaccounted — a generated
image / second-of-video / song produces no cost line. This milestone adds a NEUTRAL media-usage
record + per-media-unit pricing in generic `arnold/` so media cost is tracked, not opaque.

## Outcome

A media-producing capability call (image, video-second, audio-second, song) records a typed media
usage record, and the pricing layer prices it from per-media-unit rows into the existing
`CostResult` shape — so a media pipeline's cost is accountable end-to-end. The token path is
unchanged; media is additive. If the consumer supplies no media pricing, cost degrades GRACEFULLY
to a documented "media cost unknown" status rather than silently reading zero.

## Scope

IN:

- **A neutral `MediaUsage` record + a `media_usage` field on the usage carrier.** Add a frozen
  `MediaUsage` (e.g. `unit: str` — `"image" | "video_second" | "audio_second" | "song" | ...`;
  `count: int | float`; `dimensions: Mapping` for resolution/fps/etc.; `raw_usage`) and attach a
  `media_usage: tuple[MediaUsage, ...]` to the usage accounting. Decide the home: the token
  `CanonicalUsage` is megaplan-coupled (`pipelines/megaplan/agent/agent/usage_pricing.py`) — the
  NEUTRAL media-usage type + pricing belongs in generic `arnold/` (adjacent to the cost layer),
  not buried in the megaplan agent package, so a non-megaplan consumer (Astrid) can emit + price
  media cost without importing megaplan. (The exact generic home is an open question.)
- **Per-media-unit pricing rows.** Extend the pricing model with media rows: a `MediaPricingEntry`
  keyed by `(provider, model, unit)` → cost-per-unit (e.g. `$/image`, `$/video_second`,
  `$/song`), mirroring `PricingEntry`'s `source`/`source_url`/`pricing_version`/`fetched_at`
  provenance. Provide the same `CostStatus` ladder (`actual` / `estimated` / `included` /
  `unknown`) for media.
- **Cost computation over media usage.** Extend the cost function so a `CanonicalUsage` carrying
  `media_usage` produces `CostResult`(s) that include the media cost, summed with any token cost,
  with the correct `status`/`source`. A media usage with NO matching pricing row → `status="unknown"`
  (documented, not silently zero).
- **Emission path for a capability adapter.** A documented way for a non-model
  `StepInvocation` adapter (the AR1 non-model adapter path) to attach a `MediaUsage` to its result so the runtime
  accounts it — the media analogue of how the model adapter emits token usage. The adapter is the
  source of the media-usage record (count + dimensions); the pricing layer prices it.
- **Honest limitation doc.** If media pricing is not configured, the limitation is DOCUMENTED:
  media cost is `unknown`, the run is not blocked, and the budget caps (C2) still apply — the epic
  must not pretend opaque media cost is closed when no pricing rows exist.

OUT:

- Token-path changes — `CanonicalUsage` token fields, token pricing rows, the token cost path are
  CONSUMED unchanged.
- Media *budgets* (frame/resolution/seconds/size caps) — already built by C2; AR3 is cost
  ACCOUNTING, not budget enforcement.
- A live provider cost API for media — AR3 ships the type + the rows + the computation + the
  emission hook; populating real per-provider media rates is a data task the consumer can extend
  (provide a couple of representative rows + `official_docs_snapshot`-style provenance).
- Astrid-side: which capabilities emit which units, the actual provider rates Astrid uses.

## Locked decisions

- **Additive, never token-regressing.** `media_usage` is a new optional field; the token path is
  byte-identical. A pipeline with no media usage prices exactly as today.
- **Neutral home.** The media-usage type + media pricing live in generic `arnold/` so a
  non-megaplan consumer can use them without a megaplan import (the token `CanonicalUsage` may
  stay where it is; the media extension does not move it, it sits beside the cost layer).
- **Graceful unknown.** No matching media pricing row → `CostStatus="unknown"`, not silent zero;
  the run is never blocked on missing media pricing.
- **Reference-by-unit, not by-content.** Media usage is counted in semantic units (images,
  seconds, songs) + dimensions; it never reads the produced blob to compute cost.

## Open questions

- The exact generic home for `MediaUsage` + media pricing (a new `arnold/runtime/media_usage.py` /
  `arnold/pipeline/media_cost.py` vs. relocating a neutral cost core out of the megaplan agent
  package). Prefer the smallest neutral module that does not drag the megaplan token machinery.
  **Default: proceed with the smallest new neutral module (e.g. `arnold/pipeline/media_cost.py`) that
  does not drag the megaplan token machinery; refine in-milestone only if it fails.**
- Whether `media_usage` attaches to the token `CanonicalUsage` (one carrier, both modalities) or
  to a separate neutral usage record composed at the cost layer (avoids touching the
  megaplan-coupled type). Default: a separate neutral record, composed — to keep the token type
  untouched.
- The canonical `unit` vocabulary (open string vs. a small enum) — lean open string with a
  documented set, matching Arnold's "no opinionated literal" boundary discipline. **Default: proceed
  with an open string + a documented set (no opinionated enum); refine in-milestone only if it fails.**
- How a `CostResult` represents a mixed token+media cost (sum into one, or a tuple of results).
  **Default: proceed with a tuple of `CostResult`s (one per modality), so token and media lines stay
  separable; refine in-milestone only if it fails.**
- Whether `arnold pipeline check` (C4) should warn when a media-producing stage declares no media
  pricing source (capability-satisfiability analogue) — likely yes, as a soft warning. **Default:
  proceed with a soft warning in `arnold pipeline check` (never a hard failure); refine in-milestone
  only if it fails.**

## Constraints

- No change to the token `CanonicalUsage` fields or token pricing/cost path.
- The neutral media-usage + pricing code must not import `megaplan`.
- A pipeline with no media usage must price identically to today (regression test).
- Missing media pricing must degrade to `unknown`, never silent zero, and never block the run.
- Media cost must be computed from semantic units/dimensions, never from reading the blob.

## Done criteria

1. A neutral `MediaUsage` record (unit + count + dimensions + raw) exists in generic `arnold/` with
   no `megaplan` import, and a usage accounting carries `media_usage` additively; a test
   constructs and round-trips it.
2. Per-media-unit pricing rows (`MediaPricingEntry` keyed by provider/model/unit, with
   source/source_url/version/fetched_at provenance and the `actual/estimated/included/unknown`
   status ladder) exist; a couple of representative rows ship with documented provenance.
3. The cost computation prices a `media_usage` into `CostResult`(s) including media cost summed
   with any token cost and the correct status/source; a test prices an image + a video-second +
   a song and asserts the amounts + statuses.
4. A media usage with no matching pricing row yields `CostStatus="unknown"` (not zero) and does not
   block the run; a test asserts the unknown status + that the run proceeds.
5. A non-model `StepInvocation` adapter (the AR1 non-model adapter path) can attach a `MediaUsage` to its result and the
   runtime accounts it; a test runs the fixture adapter and reads back the media cost line.
6. The token path is unchanged: a token-only pipeline prices byte-identically to pre-AR3 (regression
   test); the token `CanonicalUsage` type is untouched.
7. The optional-media-cost limitation is documented (absent pricing → `unknown`, budgets still
   apply); media cost is computed from units/dimensions, never from blob content (test asserts no
   blob read).

## Touchpoints

- `arnold/pipelines/megaplan/agent/agent/usage_pricing.py:28` (`CanonicalUsage` — token-only;
  CONSUMED unchanged, the reference shape for the media extension)
- `arnold/pipelines/megaplan/agent/agent/usage_pricing.py:46-119` (`PricingEntry` / `CostResult` /
  `CostStatus` / `CostSource` / `_OFFICIAL_DOCS_PRICING` — the pricing shapes the media rows mirror)
- a new neutral generic `arnold/` media-usage + media-pricing + media-cost module (the genuinely-new
  code — kept megaplan-free)
- C2's media budgets (`model_seam.py` `_enforce_media_reference_budget` / `_MEDIA_FIELDS` —
  CONSUMED; AR3 is accounting, distinct from those caps)
- the AR1 non-model adapter emission path (the source of `MediaUsage`)
- optionally `arnold pipeline check` (C4) for a soft missing-media-pricing warning
- media-usage / media-pricing / mixed-cost / unknown-degrade / adapter-emission / token-regression
  tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: genuinely novel design — there is no media cost model in the tree today, and the cut
must add it as a NEUTRAL generic extension without touching the megaplan-coupled token
`CanonicalUsage`, without regressing the token cost path, and degrading gracefully to `unknown`.
It is the one place the modality story has a real gap (the ticket calls it out explicitly), and a
sloppy cut either re-couples cost to megaplan or silently reads media cost as zero. Premium/thorough/high.
