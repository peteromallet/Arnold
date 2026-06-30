# M7-sinks — Replayable Capsule + Warrant + Builder docs (the three terminal sinks)

**Status:** Milestone brief. Authoritative scope: `../validation/sequencing/PROGRAM.md` (M7-capsule
§305-312, M7-warrant §314-322, M7-docs §324-332; the three sinks are `T4`, parallelizable, hanging
off the critical path by one projection hop — §358-359), `../pipeline-unification-EPIC.md` ("The
architecture" organs §44-49, the data model §51-67), `../validation/committed-uu/SYNTHESIS.md`
(Capsule §308-314, Warrant §316-326, principles 11/12/14 §493-514), `../validation/human-blockers/REGISTER.md`
(M7 row §113, runtime-gate substitutions §52-84). Re-aims the prior single-doc draft
`m7-builder-docs.md` (which covered only docs) onto all three sinks. **Gated on M6's frozen type
surface** (relocation complete; the Manifest/Ledger/Port types stop moving).

## Outcome
The three OUTWARD-facing projections that turn the runtime into a platform, landing together because
each is a pure read-projection over the now-frozen Manifest (M5a) + the one Ledger (M4) + the Contract
Ledger (M2) — **none introduces new substrate**:
1. **Replayable Capsule** — the portable unit of exchange (Definition+Contract+Lineage+Evidence) with
   registry / inspector / fork-with-back-edge operations.
2. **Warrant** — the signed, shape-independent outward atom (authority + verified-work + decision-time
   rationale) a regulator/CISO/insurer is handed.
3. **Builder docs** (`docs/arnold/`) — the generated-from-types reference + authoring guide + worked
   examples, whose acceptance is an **external builder shipping the `select`-tournament from docs +
   scaffold ALONE with ZERO planning vocabulary** — the final proof the strangle completed.

## Scope (work items tied to current file:line)
- **Capsule schema + content-hash identity.** Add `Capsule` to `megaplan/schemas/arnold.py` (beside the
  existing `EpicEvent:239` / `EpicSnapshot:256` storage models) as four typed sub-records: **Definition**
  = the Port-graph + intent + routing (the M5a Behavioral Identity Manifest hash is the Definition's
  identity, NOT a re-hash); **Contract** = the exported Contract Ledger (M2) view — required repo@commit,
  model/tool versions, required-secrets-by-shape, Port input types — **verified BEFORE running, refusing-
  or-adapting LOUDLY** (REGISTER principle 12 §502; never the silent `TIEBREAKER→ITERATE` habit);
  **Lineage** = immutable parent edges; **Evidence** = journal + diff + verify + cost.
- **Capsule build = re-aim `store/export.py`.** `collect_epic_export(store, epic_id):27` +
  `write_epic_export_tar:120` + `_sha:19` already assemble ~80% of the bytes (state+journal+diff). Wrap
  them into `build_capsule()` that emits the FOUR named records, content-addressed via
  `BlobStore.put(blob_id, content, content_type=):42` (`blob.py`) — Evidence blobs are by-content-hash
  refs into the existing blob store, never inlined.
- **Capsule operations:** **registry** (list/get by Capsule hash), **inspector** (renders Evidence as a
  story for a cold recipient + runs the Contract check, fail-loud on unmet), **fork-with-back-edge**
  (clone Definition, append a Lineage parent edge — genealogy accretes, never flat-soup).
- **Warrant schema + emitter.** Add `Warrant` to `megaplan/schemas/arnold.py` binding: **AUTHORITY** =
  the frozen+signed policy envelope captured at action-time (model allowlist, spend ceiling + grantor,
  taint/data rules, autonomy level); **ACCOUNT** = verified-work-units in a durable owned unit decoupled
  from provider dollars; **RATIONALE ANCHOR** = captured-AT-decision-time, pinned to the Manifest hash
  (NOT replay-reconstructed — the journal's "why" re-rationalizes on replay, SYNTHESIS UU#17 §205-207);
  **SHAPE-INDEPENDENCE** — keyed to (autonomous ACTION + VERIFIED RESULT), so a one-shot action and a
  200-turn graph yield identical-shape Warrants. Sign with the existing hashing in `store/export.py:19`
  / `schemas/base.py` (HMAC-SHA256 over the frozen envelope bytes; reuse, do not invent a new crypto path).
- **`docs/arnold/` set** (no `docs/arnold/` exists today — green-field). Authored: `authoring-guide.md`,
  `package-contract.md` prose, `skill-integration.md`, `tooling.md`. **GENERATED (CI `--check`
  re-emit-and-diff)**: `reference/{pieces,nodes,drivers,control-vocabulary}.md` from the M2-M5c typed
  surface, the manifest field table, and the checker error catalogue. The generator reads
  `registry.read_skill_md:137` + `discover_python_pipelines:360` (`_pipeline/registry.py`) for the package
  contract; examples are **extracted from real in-tree packs** (jokes / select-tournament / planning-as-
  composition), never hand-maintained.
- **External-builder acceptance harness** — a sandboxed subagent given ONLY `docs/arnold/` + scaffold
  output (no SDK internals), driving `new → wire select+reduce → SKILL.md → pipelines check → doctor →
  arnold run`, with a grep asserting zero `GateRecommendation`/`STATE_*`/4-verdict in the builder's module.

## Locked decisions
- **The milestone given (`m7-sinks`) bundles PROGRAM's three independent sinks** (M7-capsule ∥ M7-warrant
  ∥ M7-docs, §358-359). Internally three parallel PRs; only the docs PR hard-gates on the frozen post-M6
  type surface — Capsule and Warrant gate on Manifest+Ledger which froze at M6 too, so all three may land
  in this one milestone.
- **Pure projection — adds no new substrate** (PROGRAM §312). Capsule/Warrant READ the one Ledger
  (recorded-into, never recomputed-from, SYNTHESIS reshaper #5); they record nothing new. This keeps them
  off the strangler critical path: a red sink is "don't publish," never a broken live engine.
- **Generation rule** (from prior draft, retained): if a fact is also a type/enum/manifest-field/node-
  signature, the doc is generated and CI-diffed; prose explains why/when. `reference/`, the manifest
  table, the checker catalogue, the umbrella skill = generated; guide/examples/skill-integration/contract
  prose = authored.
- **Examples extracted from real packs** (`registry.discover_python_pipelines:360`), never snippets — CI
  extracts each from its source pack and runs it.
- **Refuse-or-adapt LOUDLY** is the Capsule Contract law and the Warrant's whole point (REGISTER §502;
  SYNTHESIS principle 12) — silence on rehydration is forbidden.

## Open questions (each RESOLVED to its default — zero human blockers)
- **Does the umbrella skill replace or compose megaplan-decision/observe/epic?** → **COMPOSES** (does not
  replace) during the rename; boundary: module-specific guidance → per-package `SKILL.md`, cross-module →
  `docs/arnold/` (REGISTER M7 §113).
- **Where does per-module SKILL.md end and umbrella how-to begin?** → module-specific in SKILL.md, cross-
  module in `docs/arnold/` (above); the generated skill-integration doc states the split so it can't drift.
- **Warrant signing key / identity authority?** → reuse the existing `store/export.py:19` SHA path with an
  HMAC key from the run's config-precedence resolver (M4); no new key-management surface, no human enroll.
- **Capsule Contract check failure at rehydration?** → fail LOUD with the machine-readable repair gradient
  the Contract Ledger already emits (M2: "needs X, has Y; legal moves …"); auto-adapt if a legal coercion
  exists, else refuse — never silently degrade (REGISTER §502).
- **External-builder acceptance red?** → auto-file the doc-gap ticket and retry with a stronger model
  (REGISTER M7 §113); criteria are all exit-code/artifact/grep, no human review.
- **What is the fourth (non-planning) tool / cheap new pipeline?** → `select`-tournament (shared with the
  acceptance test) / upgrade `jokes` (REGISTER M6 §112).

## Constraints
- The reference generator MUST run against the FINAL post-M6 typed surface; generators may be scaffolded
  incrementally beside each type addition in M2-M5c, but the committed, acceptance-tested set is THIS
  milestone (prior draft §46-48).
- Capsule/Warrant are READ-ONLY over the one Ledger — they may not write back into it nor recompute truth
  (reshaper #5). Evidence/Lineage are folded from the log, not re-derived heuristically.
- Strangler discipline still applies even for sinks: they land behind a default-OFF flag beside the
  existing `collect_epic_export` path; the old export path is not deleted in this PR (PROGRAM §374-379 —
  no organ-swap + old-path-deletion in one PR). The sole retirement authority remains the behavioral-
  replay + substrate-swap oracle, never the happy-path parity gate (§381-386).
- All back-compat held: `extra="ignore"`, schema_version stamped & validated (report-only per M4 default),
  preserve `MEGAPLAN_*` env, `__all__` shims.

## Done criteria (testable, incl. this milestone's oracle gate)
1. **Capsule round-trip oracle (the sink's substrate-swap gate):** `build_capsule(epic_id)` → write →
   `inspect` on a DIFFERENT process/version reconstructs Definition+Contract+Lineage+Evidence
   byte-identically from blob refs; the Contract check fails LOUD (non-zero) when a required
   repo@commit/model-version/secret-shape is unmet, and adapts via a legal coercion when one exists.
   `fork-with-back-edge` produces a child whose Lineage contains exactly one parent edge to the source hash.
2. **Warrant shape-independence test:** a one-shot action and a multi-step graph over the SAME verified
   result emit Warrants with identical field shape; the RATIONALE ANCHOR equals the decision-time capture
   (NOT a replay re-render — assert it survives a re-run that would re-rationalize); the AUTHORITY envelope
   is signed and signature-verifies; tampering any envelope byte fails verification.
3. **External-builder acceptance (the headline gate):** a sandboxed subagent with ONLY `docs/arnold/` +
   scaffold ships the `select`-tournament — `new` → wire `select`+`reduce` → author `SKILL.md` →
   `pipelines check` exits 0 → `pipelines doctor` shows `discovered ✓` → `arnold run` produces the winner
   artifact — and a grep asserts **zero `GateRecommendation`/`STATE_*`/4-verdict** in the builder's module.
   (`JoinFn` returning `GateRecommendation` at `_pipeline/pattern_types.py:16-19` is the leak this proves
   sealed; the grep gate has been ON since M1.)
4. **Reference drift gate green:** `docs/arnold/reference/*` regenerates byte-identically under CI
   `--check` (re-emit-and-diff joins the M1 anti-drift gates); byte-non-identical auto-fails.
5. **Examples-run gate:** every `docs/arnold/examples/*` snippet is extracted from a real in-tree pack
   (jokes / select-tournament / planning-as-composition) and runs green in CI.
6. **Strangler invariant:** OLD engine still self-hosts a throwaway 1-milestone plan (frozen pinned venv,
   flag-off) AND a planning-shaped throwaway runs on the new organs behind the default-OFF flag with the
   behavioral-replay oracle green; the old `collect_epic_export` path remains live and undeleted.

## Touchpoints
`megaplan/schemas/arnold.py` (+`Capsule`, +`Warrant` storage models, beside `EpicEvent:239`),
`megaplan/store/export.py` (`collect_epic_export:27`, `write_epic_export_tar:120`, `_sha:19` → wrapped by
`build_capsule`), `megaplan/store/blob.py` (`BlobStore.put:42`/`get:45` for Evidence refs),
`megaplan/_pipeline/registry.py` (`read_skill_md:137`, `discover_python_pipelines:360` — package-contract
generator source), `megaplan/schemas/base.py` (signing reuse), the `pipelines` CLI group (`new`/`check`/
`doctor`, land in M1), `docs/arnold/` (new), `megaplan/data/_*` + `~/.claude/skills/arnold*` (skill
generation), the M2-M5c typed surfaces (Manifest, Port, Contract Ledger, control vocabulary, node lib).

## Anti-scope
- **No new SDK capability** — this milestone only PROJECTS what M1-M6 built; no change to the pieces, no
  new substrate, no new organ (PROGRAM §312, prior draft §63).
- **No retirement of the old export path** in this PR (strangler: swap and old-path deletion never share a
  PR; that deletion, if ever, rides a later dual-green milestone — not a sink).
- **No demand/business work** — the category bet is settled (EPIC banner §3-21); sinks are built from
  conviction, not gated on a buyer.
- **Not the M6 relocation/namespace work** — `arnold <verb>` migration + `_BUILTIN_NAMES` drop is M6; this
  milestone consumes its frozen output.
- **No re-hashing of identity** — the Capsule Definition IS the M5a Manifest hash; the Warrant rationale IS
  pinned to it; do not introduce a fourth identity string (SYNTHESIS principle 3 §455-457).
