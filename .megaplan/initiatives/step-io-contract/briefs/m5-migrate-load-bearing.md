# M5: Migrate + Delete the Load-Bearing Five

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Migrate the four remaining load-bearing IO sites onto the contract and delete their old stringly-typed paths as each is migrated. The migration surface is 33 distinct IO sites (19 inbound prompt-assembly + 14 outbound parse/validate); the load-bearing 5 are execute, finalize, critique, review, gate. Execute is already done as m3's proving ground, so m5 takes finalize, critique, review, and gate.

The real win is REMOVAL: kill `_normalize_worker_payload`'s fuzzy key-drift patching, make execute's `validate_payload` batch-relaxation a native contract mode (retiring the key-presence-only `validate_payload`), and preserve the behaviors that matter — `_recover_codex_payload`'s 3 fallbacks and `compact_review_prompt`'s compaction. Old paths are deleted PER-SITE as each is migrated, not in a big-bang.

## Scope

IN:

- Migrate finalize, critique, review, and gate onto the contract: inbound prompt-assembly through `render_step_message` (m3), outbound parse/validate through `capture_step_output` + the structural audit (m0b/m3).
- Per-site DELETE of the old stringly-typed path as each of the four sites is migrated (not a deferred bulk cleanup).
- Kill `_normalize_worker_payload`'s fuzzy key-drift patching once the sites that relied on it are on the contract.
- Make execute's batch-relaxed validation a NATIVE contract mode and retire the key-presence-only `validate_payload` (`workers/_impl.py:1853`) for these sites.
- Preserve the behaviors the contract must keep: `_recover_codex_payload`'s 3 fallbacks, critique completeness scoring, and `compact_review_prompt`'s compaction (expressed as the unified contract's compaction mode).
- Roll out per seam shadow-first via m1, promoting to enforce off telemetry.
- Tests per migrated site: contract round-trip, old-path removal, preserved-behavior (Codex fallbacks, critique completeness, review compaction).

OUT:

- The ~28-site long tail (m6).
- Execute (already migrated in m3).
- Model-seam machinery itself (m3 owns `render_step_message`/`capture_step_output`); m5 CONSUMES it.
- Suspension composition (m4) and authoring-API enforcement (m7).
- Any new validator/registry/chokepoint.

## Locked Decisions

- Migrate the load-bearing 5 first; execute is done in m3, so m5 covers finalize/critique/review/gate.
- DELETE old stringly-typed paths PER-SITE as migrated, not in a big-bang (Opus adjudication).
- Kill `_normalize_worker_payload` fuzzy key-drift patching.
- Make execute's `validate_payload` batch-relaxation native to the contract (retire key-presence-only validation for migrated sites).
- Preserve `_recover_codex_payload`'s 3 fallbacks, critique completeness scoring, and `compact_review_prompt` compaction as a contract compaction mode.
- Roll out shadow-first per seam via m1; promote off telemetry.

## Open Questions

- Migration order among finalize/critique/review/gate and which to promote to enforce first based on telemetry.
- How `compact_review_prompt`'s compaction is expressed in the unified contract (a compaction mode on `render_step_message` vs. a separate pass) without losing review fidelity.
- How critique completeness scoring maps onto the typed output contract (a validated field vs. a post-validation computation).
- Whether `_normalize_worker_payload` can be deleted outright after these four sites or whether long-tail sites (m6) still depend on it (sequencing the kill).
- The exact native expression of batch-relaxation per the finalize/gate batch shapes.

## Constraints

- Each old path is deleted only after its site is on the contract and validated — no dangling dual paths left behind.
- Preserved behaviors (Codex fallbacks, critique completeness, review compaction) must be demonstrably intact post-migration.
- No regression to the un-migrated long-tail sites that may still share helpers.
- Shadow-first rollout; no seam jumps to enforce without telemetry.
- Bases on m0a/m0b/m1/m2/m3; consumes the model-seam machinery without modifying it.

## Done Criteria

1. Finalize, critique, review, and gate are migrated onto the contract (assembly via `render_step_message`, output via `capture_step_output` + structural audit); each round-trips through the m1 chokepoint (tests).
2. The old stringly-typed path for each of the four sites is DELETED as part of that site's migration; tests confirm the old path is gone, not merely bypassed.
3. `_normalize_worker_payload` fuzzy key-drift patching is removed (or scoped for m6 if a long-tail dependency is proven), with a test asserting migrated sites no longer call it.
4. Execute's batch-relaxed validation is a native contract mode and key-presence-only `validate_payload` is retired for the migrated sites (test).
5. `_recover_codex_payload`'s 3 fallbacks, critique completeness scoring, and `compact_review_prompt` compaction are preserved and tested post-migration.
6. Each migrated seam can run shadow→enforce via m1; tests cover at least one site at enforce rejecting a bad output.

## Touchpoints

- `megaplan/handlers/finalize.py`, `megaplan/handlers/critique.py`, `megaplan/handlers/review.py`, `megaplan/handlers/gate.py`
- `_normalize_worker_payload` (deletion)
- `megaplan/workers/_impl.py:1853` (`validate_payload` — retired for migrated sites; batch-relaxation made native)
- `_recover_codex_payload` (preserve 3 fallbacks)
- `compact_review_prompt` (compaction mode in the contract)
- critique completeness scoring
- m3 `render_step_message`/`capture_step_output`, m0b validator, m1 chokepoint/telemetry (consumed)
- per-site migration + old-path-removal + preserved-behavior tests

## Rubric

- Profile: `partnered`
- Robustness: `full`
- Depth: `medium`

Rationale: these are the four highest-traffic remaining stages, but the hard design problems (the type, the validator, the model-seam machinery, shadow rollout) are already solved upstream — m5 is disciplined application plus careful per-site deletion with behavior preservation. Full robustness guards the deletions and preserved behaviors; medium depth and partnered tier fit applied migration work that leans on settled foundations rather than novel design.
