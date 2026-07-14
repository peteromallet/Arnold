# Structured phase boundary cleanup

Date: 2026-07-13 UTC

Initiative: Workflow Boundary Contracts corrective

Scope: all 17 registered Megaplan structured phase identities

## Outcome

The `north_star_actions` incident was a producer-normalizer-validator contract
failure, not a gate-schema failure. Regression `3ff595994e` introduced a
handwritten gate capture projection that omitted the already schema-owned
field. The worker kept producing it, the normalizer deleted it, and the strict
validator correctly rejected the damaged payload. State history contains 51
identical failures from `2026-07-13T15:55:42Z` through
`2026-07-13T17:39:37Z` (the final matching event is stamped
`2026-07-13T17:39:36Z`), followed by gate success at
`2026-07-13T17:44:41Z` and finalize success at `2026-07-13T17:48:26Z`.

Commit `94abc498ec` repairs the original gate path. This follow-through removes
the analogous handwritten projections found in review, critique, execute, prep
distill, and finalize, adds a capture-time preservation assertion, and gives
each lossy compatibility transform an explicit owner. The existing three-
identical-phase-failure breaker from `f0cc3e61e5` contains deterministic retry
amplification across phases; no chain control state was changed during this
work.

## Coverage inventory

Every row below was checked against `STEP_CONTRACTS`, the runtime schema
registry, template registry, capture seam, phase handler/orchestrator, and
durable readers. "Direct" means no lossy compatibility projection exists: the
captured mapping is schema-audited without a field allowlist.

| Phase | Producer / projection | Validator | Persistence and reload | Retry / repair | Result |
|---|---|---|---|---|---|
| `execute` | batch workers; one shared schema-derived task/ack projection plus named evidence-envelope extensions | relaxed batch capture, then `execution.json`/handler checks | batch artifacts and `finalize.json`; authority/completion readers rehydrate task state | auto phase breaker; repair fingerprint and custody tests | duplicate normalizer removed; nested drift test added |
| `finalize` | file-fill `finalize_output.json`; schema-derived input scratch projection; nullable task optionals are the only declared lossy adapter | explicit input schema, final `finalize.json`, semantic postchecks | `finalize.json`, `finalize_snapshot.json`, `contract.json`; execute/review/completion/authority readers | common breaker and repair loop | input now requires every model-owned persisted field |
| `critique` | pre-populated file-fill / parallel workers; schema-derived top, check, finding, and flag projections | `critique.json` plus critique semantic checks | `critique_v*.json`, evaluator artifacts; gate/revise reload flags | common breaker; candidate recovery re-audits | handwritten nested allowlists removed |
| `review` | pre-populated file-fill / parallel workers; schema-derived scratch and template plus named `review_completion_status` control extension | `review.json` plus evidence/completion audit | `review.json`, evidence and authority transition artifacts; auto/completion reload | common breaker; authoritative raw promotion re-audits | residual `north_star_actions` omission fixed |
| `gate` | file-fill worker; schema-derived template, scratch promotion, normalization, carry, and finalize projection | closed `gate.json` plus gate semantic checks | `gate.json`, `gate_carry.json`, signals; critique/finalize/auto reload | common breaker; passing artifact reconciliation | original incident path fixed by `94abc498ec` |
| `plan` | Markdown/provider structured capture; schema-derived base projection followed by semantic metadata extraction | `plan.json` / plan structure checks | `plan_v*.md` and metadata; critique/gate/test-selection reload | common breaker and model recovery | future top-level schema fields now survive |
| `prep` | orchestrated prep pipeline; direct capture except the distill compatibility substep | `prep.json` | `prep.json`, dossier, metrics, research; plan prompt reload | common breaker | no independent lossy boundary found |
| `critique_evaluator` | file-fill worker; schema-derived scratch top level plus variant-specific semantic normalization | `critique_evaluator.json` (`oneOf` selection variants) | `evaluator_verdict_v*.json` and latest verdict; critique reload | common breaker; invalid candidate recovery | scratch drift closed; variant adapter retained explicitly |
| `revise` | Markdown/provider structured capture; direct schema audit and plan-version writer | `revise.json` plus plan structure and north-star-addressed checks | new `plan_v*.md` and metadata; next critique/gate reload | common breaker and candidate recovery | no handwritten field projection found |
| `prep-triage` | research orchestrator substep; direct capture | `prep_triage.json` | `prep_triage.json`; prep research reload | common breaker at owning prep phase | no lossy boundary found |
| `prep-distill` | research orchestrator substep; schema-derived nested alias adapters | `prep.json` | canonical `prep.json`; plan reload | common breaker at owning prep phase | four nested handwritten projections removed |
| `prep-research` | per-area research worker; direct capture | `prep_research_finding.json` | Hermes state and `research.json`; distill reload | owning prep retry/partial-result policy | no lossy boundary found |
| `feedback` | feedback worker; direct capture | `feedback.json` | feedback artifact / consumer handoff | common phase breaker | no lossy boundary found |
| `loop_plan` | loop worker; direct loop schema (the registry's `normalizer=plan` is routing metadata, not an applied plan-field allowlist) | `loop_plan.json` | loop state/artifacts consumed by loop controller | common phase breaker / fallback guard | no lossy boundary found |
| `loop_execute` | loop worker; direct loop schema | `loop_execute.json` | loop state/artifacts consumed by loop controller | common phase breaker / fallback guard | no lossy boundary found |
| `tiebreaker_researcher` | tiebreaker subloop; direct structured capture | `tiebreaker_researcher.json` | numbered researcher artifacts; tiebreaker reload | owning gate phase breaker | no lossy boundary found |
| `tiebreaker_challenger` | tiebreaker subloop; direct structured capture | `tiebreaker_challenger.json` | numbered challenger artifacts; tiebreaker reload | owning gate phase breaker | no lossy boundary found |

Runtime provenance was also checked: the cloud refresh path verifies the
expected engine root and revision, and the regression test introduced with
`94abc498ec` covers that fail-closed check. The active corrective cloud chain
was observed read-only and was neither restarted, paused, nor advanced by this
audit.

## Residual gaps and risk ranking

### P0, closed in this corrective branch

1. Gate schema field loss between worker output and validation.
2. Equivalent handwritten top-level and nested projections in review,
   critique, execute, and prep distill.
3. Finalize scratch accepting omission of model-owned persisted fields.
4. No runtime attribution when a normalizer deletes a schema-owned field.
5. Unbounded identical deterministic phase retries (closed by `f0cc3e61e5`,
   verified here rather than reimplemented).

### P1, bounded residual risk

1. Boundary receipts do not yet persist raw/normalized/canonical key sets and
   hashes for every legacy phase. The new runtime guard detects schema-owned
   field deletion before validation, but it is not a full immutable transform
   receipt.
2. The preservation walk follows ordinary object/array schemas. It deliberately
   does not infer ownership through `oneOf` variants or treat array-element
   filtering as a field deletion. The only current `oneOf` normalizer is the
   critique evaluator's explicit variant adapter; no current model-owned array
   normalizer was found that filters whole elements.
3. Provenance pins the deployed engine root/revision at refresh time, not a
   separately hashed schema/projection bundle on every phase receipt.
4. The implementation commits are not part of the currently running cloud
   revision until normal merge/deploy/refresh occurs. Mutating the active chain
   to prove rollout was intentionally outside this run's custody constraints.

### Pre-existing unrelated test debt

The broader slice exposes four failures in
`tests/m8/test_outbound_coverage_catalog.py` and two in
`tests/orchestration/test_full_suite_backstop.py`. A separate broad retry suite
also exposes the stale acceptance assertion in
`tests/cloud/test_meta_repair_wrapper_retrigger.py::test_retrigger_helper_passes_workspace_and_remote_spec`:
the verifier now correctly treats process-only terminal evidence as
provisional, while the test still expects acceptance. All seven reproduce on the
untouched parent `6c0a7b1e9a`: the outbound catalog is stale relative to many
existing call sites, while the backstop shadow/enforce expectations do not
match current chain behavior. These failures were investigated and left unchanged
because none is caused by, or safely repaired within, structured
phase projection scope.

An additional prompt/semantics compatibility slice has 78 passing tests and 12
stale `test_semantics_carrier.py` expectations (component counts and handler
purity assertions). The identical 78/12 result reproduces on parent
`6c0a7b1e9a`; the schema-carrier table and prompt worktree checks themselves
pass.

## Verification

- Focused structured-boundary suite: 100 passed on the rebased final code.
- Boundary, retry, repair, provenance, and north-star regression suite: 803
  passed, 1 pre-existing stale meta-repair assertion failed; the failure was
  reproduced alone on parent `6c0a7b1e9a`.
- Additional compatibility slice: 153 passed, 6 failed; the same 6 failures
  reproduced on parent `6c0a7b1e9a` (17 passed, 6 failed in the two affected
  files).
- Prior corrective evidence: 345 focused tests passed for model seam recovery,
  auto blocked recovery, repair custody/meta-repair/progress auditor, and
  status behavior.

Final commit identifiers and the last regression rerun are recorded in the
commit history and delivery summary after validation.

## Confidence

Confidence is high for the enumerated schema-owned field-loss class across all
17 registered Megaplan phases: every phase was inventoried, every active lossy
projection found was made schema-derived or explicitly declared, the capture
seam now rejects undeclared field loss before blaming validation, and the
focused/broad regression paths pass. Overall confidence is medium-high rather
than absolute because transform receipts, `oneOf`/array-element semantic
provenance, and production rollout remain explicit P1/operator concerns.
