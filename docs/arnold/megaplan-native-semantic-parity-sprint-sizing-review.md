# Megaplan Native Semantic Parity Sprint Sizing Review

Generated: 2026-07-09

Inputs:

- `docs/arnold/megaplan-native-semantic-parity-master-plan.md`
- `docs/arnold/megaplan-native-parity-existing-work-swarm-synthesis.md`
- Three Codex `gpt-5.6-sol` read-only reviews under
  `.tmp/native-parity-sprint-sizing-codex/`

## Verdict

Keep the 15-sprint spine as the default execution plan.

The existing-work swarm does not justify broadly compressing the plan. It reduces
implementation uncertainty inside several sprints, especially execute scheduling,
override/control, native runtime substrate, and evidence generation. But the work
remaining is not mostly invention; it is source-authority cutover, removal or
fencing of competing route brains, dead-delete proof, deterministic parity
evidence, and installed-package verification. Those are exactly the controls
that prevent another representational false pass.

The 15-sprint plan is best understood as a staffed, aggressive two-week cadence,
not a single-engineer estimate. It should be run with parallel implementation,
fixture, checker, and adversarial-review work inside each sprint.

## Codex Review Split

The reviewers disagreed in a useful way:

- Compression review: recommended 13 sprints by merging S1c+S1d and S4a+S4b.
- Adversarial review: recommended 19 sprints by splitting S0, S2b, S4b, S6b, and
  S7.
- Rationale review: recommended keeping 15 sprints, with clearer ownership and
  strict per-sprint rationale.

My synthesis: keep 15 by default, but encode merge and split triggers.

## Conditional Merge Triggers

Two merges are defensible only if the sprint starts with prerequisite proof
already green:

1. **S1c + S1d** can merge if generic runtime fanout/suspension proof,
   Megaplan-specific manifest dispatch tests, and typed outcome surfaces are
   already passing before the sprint begins. Otherwise keep them separate.
2. **S4a + S4b** can merge only if the first half proves lowered-source execute
   fanout and old scheduler authority is dead-deleted by the midpoint. If the
   midpoint proof fails, split immediately.

These are optional acceleration paths, not the base plan.

## Split Triggers

Split a sprint rather than forcing closure if any trigger appears:

- **S0** splits if runner pinning/clean-context auditor work blocks the
  gate-carry/revise action path.
- **S1a** splits if package-wide carrier classification surfaces far more
  route-authoritative carriers than expected. Do not move replay/baselines into
  S1a; that belongs to S1b.
- **S2b** splits if gate decision/preflight authority and revise reentry/caps
  cannot both close with independent scenarios and dead-delete proof.
- **S4b** splits if approval/recovery and fresh-session/partial-resume fixtures
  start contending for different rollback strategies.
- **S6b** splits if auto-drive authority collapse and manifest/compatibility
  quarantine require separate rollout decisions.
- **S7** splits into S7a/S7b if final evidence tooling was not fully built and
  dry-run during S1-S6.

## Ownership Correction

The master plan's spine assigns:

- S1a: checker authority, row registry, carrier scan, structural rejection.
- S1b: deterministic replay, control injection, scenarios, baseline freeze.

The detailed S1a section still includes some S1b work. Sprint briefs should
enforce the spine ownership above. S1a is not two-week plausible if it also owns
replay harness, baseline freeze, and headless control injection.

## Sprint Rationale

| Sprint | Main work | Existing assets to reuse | Why this is an aggressive two-week sprint | Merge stance |
| --- | --- | --- | --- | --- |
| S0 - Runner Pinning and North Star Action Plumbing | Pin runner; add structured North Star actions through gate/carry/revise/review/finalize; enforce blocking severity and clean-context review. | Gate carry path, revise feedback plumbing, runtime schemas, runner identity concepts. | The data path exists, but schemas, enforcement, canaries, post-validation, and pinning are new. Two parallel workstreams make this tight but bounded. | Do not merge. It governs every later sprint. |
| S1a - Checker Authority, Registry, Carrier Scan, Rejection | Strict checker authority, external row registry, package-wide carrier scan/classification/reconciliation, structural diagnostics, current-shape negative fixture. | `source_compiler.py`, row-evidence tests, `semantic_evidence.py`, boundary contracts, old evidence-generator scan shapes. | Extends real checker machinery, but scanner/registry/diagnostics/fixtures are substantial. Plausible only if replay/baseline work is excluded. | Do not merge with extraction or S1b. |
| S1b - Deterministic Evidence Substrate and Baseline Freeze | Canned-payload replay, split-outcome scenario validation, headless control injection, baseline freeze/amendment protection. | `ReplayCursor`, `semantic_replay.py`, native goldens, scenarios YAML, installed-package smoke patterns. | Comparison vocabulary exists, but deterministic golden harness and interactive branch injection are new integration work. | Do not merge with S1a. Checker proof and behavior oracle must be independent. |
| S1c - Runtime Substrate and Manifest Source Dispatch Proof | Prove Megaplan dynamic fanout, suspension/reentry, loop-exit strategy, and source-derived manifest dispatch for tested path. | Native compiler/runtime fanout and suspension support, generic runtime tests, lowered-source topology. | Generic runtime exists; Megaplan dispatch integration and serialized-plan behavior are the sprint. | Conditional merge with S1d only if substrate proof is already green. |
| S1d - Typed Outcomes and First Builder Edge | Make one real builder edge source-owned, consume typed outcomes, remove component route dependence, prove installed and dead-delete parity. | Typed outcomes, source topology helpers, existing builder. | Deliberately thin vertical slice; mutation and installed-package proof prevent a cosmetic demo. | Usually keep separate as learning checkpoint. |
| S2a - Prep, Plan, Critique Native Authority | Move prep/plan/critique authority into canonical source or named native workflow and fence old carriers. | Front-half skeleton, `front_half.pypeline`, native goldens, phase bodies, artifact contracts. | Linear phase group with existing shape; work is authority transfer, scenarios, and deletion proof. | Keep separate from gate/revise. |
| S2b - Gate and Revise Native Loop | Extract gate branches, reprompt/downgrade, debt/no-progress termination, revise reentry, caps, and suspension semantics. | Gate/revise handlers, critique runtime feedback, typed outcomes, goldens. | Behavior exists but route authority must move without changing artifacts/caps/resume behavior. This is tight. | Do not merge; split if gate and revise loop proofs diverge. |
| S3 - Tiebreaker and Replan Native Flow | Turn four visible phases into semantic source authority and prove replan rejoin/reset. | Four source-visible phases, typed outcome, boundary contracts, replan helper. | Topology is sketched, but current source is partly cosmetic. Four phases plus rejoin/deletion fill the sprint. | Keep separate. |
| S4a - Execute DAG and Scheduling Hardening | Prove dynamic batches end to end; extract dependency scheduling, fanout/fanin, tier/model binding, batch splitting, handoff decisions. | Pure scheduling functions, topology scheduler, `execute/batch.py`, execute policy, native `parallel_map`. | Strong reuse makes this hardening/extraction rather than build. Time goes to runtime-path proof and hidden scheduler deletion. | Conditional merge with S4b only with midpoint proof. |
| S4b - Execute Approval, Retry, Fresh Session, Partial Resume | Extract destructive approval/denial, blocked retry, fresh-session forcing, partial resume, recovery, no-review handoff. | Execute policy, handler behavior, control paths, resume schemas, goldens. | Policy exists, but interactive control, suspension, recovery, and serialized compatibility are integration-heavy. | Keep separate unless S4a midpoint is green and scope remains stable. |
| S5a - Review Fanout, Rework, Caps | Extract review fanout/fanin, reducer decisions, pass/rework branches, cap behavior, rework reentry. | Visible review topology, `ReviewOutcome`, policies, handler behavior, receipt contracts. | Existing scaffolding helps, but current checker false-passes on policy mappings. Source constructs, negative fixtures, cap scenarios, and dead-delete make it full. | Do not merge with finalize. |
| S5b - Finalize Fallback and Terminal Projection | Extract finalize fallback, no-review/deferred-human terminals, final artifact projection, terminal route selection. | Finalize handlers, fallback/baseline logic, artifact contracts, existing labels. | Code volume may look small, but terminal correctness has high blast radius and every terminal outcome needs proof. | Keep separate. |
| S6a - Override and Human Control Surface Collapse | Collapse handler, matrix, control-interface, and feature-flag paths into one source-visible authority. | `override_matrix.py`, override handler, `AuthorityRecord`, `ControlTransition`, boundary receipts. | Surface is built, but matrix is not authority. State/action matrix, invalid-state tests, and split-brain removal fill the sprint. | Do not merge with auto/compat. |
| S6b - Auto, Manifest Backend, Compatibility Quarantine | Remove auto next-step derivation and route-dispatch fallback as independent brains; make manifest consume lowered source; quarantine compat/CLI projections. | Manifest backend, auto-drive corpus, compatibility scans, deleted-surface/coupling tests, S1 source-dispatch slice. | Wide deletion-heavy authority collapse. Existing code reduces discovery, not blast radius. | Keep separate; split if auto and compat need distinct rollout policy. |
| S7 - Final Generated Conformance and Rollout | Rerun/aggregate strict checkout and installed checks, full reconciliation, baselines, scenario-row coverage, mutation, exemptions, rollout/resume policy, generated report. | Generalized evidence generator, validators, scenarios, goldens, installed-wheel smoke, deleted-surface/coupling tests, all S1 tooling. | Pulling tooling forward keeps this from becoming implementation, but final package reconciliation and rollout are still full-sprint work. | Do not merge. Split into S7a/S7b if tooling is not already dry-run clean. |

## Recommendation

Do not condense the plan now. Keep the 15-sprint spine, fix S1a/S1b ownership,
and document conditional merge/split triggers.

The plan is already aggressive. Existing work should be used to make each sprint
more reliable and less exploratory, not to remove the independent proof
boundaries that prevent false closure.
