# M6: Migrate + Delete the Long Tail

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Finish the migration: take the ~28-site long tail of the 33-site IO surface onto the contract and delete each site's old stringly-typed path as it lands. The load-bearing 5 are done (execute in m3, the rest in m5); m6 sweeps the remaining inbound prompt-assembly (f-string concat) and outbound parse/validate (regex recovery) sites.

The point of this milestone is REMOVAL of the old seams, not addition of a new one. With the long tail migrated, the legacy stringly-typed crossing — f-string prompt concatenation and regex-based output recovery — is deleted across the codebase, leaving the contract as the single way a step crosses a model or data boundary.

## Scope

IN:

- Migrate the ~28 remaining IO sites onto the contract: inbound prompt-assembly via `render_step_message` (m3), outbound parse/validate via `capture_step_output` + the structural audit (m0b/m3).
- Per-site DELETE of the old path as each site lands: remove f-string prompt concatenation and regex-based output recovery at that site.
- Roll out shadow-first per seam via m1, promoting to enforce off telemetry.
- Finish the kill of any shared legacy helpers (e.g. residual `_normalize_worker_payload` usage) once their last long-tail caller is migrated.
- Tests per migrated site (or per cohort, given volume): contract round-trip and old-path removal.

OUT:

- The load-bearing 5 (m3 + m5).
- Model-seam machinery itself (consumed from m3).
- Suspension composition (m4) and authoring-API enforcement (m7).
- Any new validator/registry/chokepoint.
- The acceptance gate / regression proof (m8).

## Locked Decisions

- Migrate the ~28-site long tail; per-site DELETE of f-string concat + regex recovery as each lands (Opus adjudication: delete-old-paths per-site, not big-bang).
- The real win is REMOVING old seams, not adding a new one.
- Roll out shadow-first per seam via m1; promote off telemetry.

## Open Questions

- Cohorting strategy for ~28 sites: per-site PRs vs. grouped by handler/family, and how tests are scoped to keep the volume tractable.
- Which long-tail sites are safe to promote straight to enforce vs. which need a shadow soak given lower traffic.
- Whether any long-tail site has a quirk (custom recovery, multi-output) that needs a contract feature not exercised by the load-bearing 5.
- Final retirement point for shared legacy helpers once their last long-tail caller is gone.
- Whether any of the 28 sites is actually dead/unused and should be deleted rather than migrated.

## Constraints

- Each old path is deleted only after its site is on the contract and validated.
- No dual legacy/contract path may be left dangling at a migrated site.
- The long-tail volume must not regress the load-bearing 5 or shared helpers they still rely on until the last caller is migrated.
- Shadow-first rollout; no seam jumps to enforce without telemetry.
- Bases on m0a/m0b/m1/m2/m3/m5; consumes the model-seam machinery without modifying it.

## Done Criteria

1. The ~28 long-tail IO sites are migrated onto the contract; each round-trips through the m1 chokepoint (tests, scoped per-site or per-cohort).
2. F-string prompt concatenation and regex-based output recovery are DELETED at each migrated site; tests confirm the old paths are gone, not bypassed.
3. Any remaining shared legacy helper (e.g. residual `_normalize_worker_payload`) is removed once its last caller is migrated; a test asserts no live caller remains.
4. Each migrated seam can run shadow→enforce via m1; a representative sample is promoted to enforce and rejects a bad output (test).
5. After m6, the contract is the single crossing mechanism for the migrated surface — no legacy stringly-typed prompt-assembly or output-recovery path survives at a migrated site.
6. No load-bearing-5 regression; their tests still pass.

## Touchpoints

- the ~28 long-tail inbound prompt-assembly sites (f-string concat) and outbound parse/validate sites (regex recovery) across handlers/prompts/workers
- residual `_normalize_worker_payload` and other shared legacy helpers (final removal)
- m3 `render_step_message`/`capture_step_output`, m0b validator, m1 chokepoint/telemetry (consumed)
- per-site / per-cohort migration + old-path-removal tests

## Rubric

- Profile: `directed`
- Robustness: `full`
- Depth: `medium`

Rationale: this is high-volume, low-novelty cleanup — ~28 mechanical migrations against a fully-settled contract and machinery, where the value is breadth and the disciplined per-site deletion of dead paths. Directed tier fits the repetitive applied work; full robustness guards the deletions (the easiest place to silently break a low-traffic site); medium depth reflects that the design questions were answered upstream.
