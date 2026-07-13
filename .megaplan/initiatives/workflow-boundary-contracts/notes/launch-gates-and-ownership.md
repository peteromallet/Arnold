# Launch Gates And Ownership Boundaries

This note is the operator contract for launching the corrective WBC chain.

## Chain-Level Launch Gates

The Run Authority gate is enforced by `chain.yaml` as a `chain_completed`
precondition with `require_manifest: true`. Megaplan Maintenance is explicitly
independent and is not a chain launch precondition.

### Gate RA: Run Authority Complete

The canonical three-milestone Run Authority chain is landed on `main` and its
completion manifest matches the current chain spec, North Star, all three
briefs, chain state, milestone plan identities, merge evidence, and deliberate
proof artifacts.

The proof map must demonstrate:

1. foundation: generic kernel contracts, authority input inventory, deterministic
   shadow `RunAuthorityView`/`PlanExecutionView`, and separate runner/publication
   diagnostics;
2. enforcement: dispatch grants and attempt identity, one merge/reconcile
   validator, quarantine/rejection of off-scope or stale results, and ready
   frontier from accepted attempts/dependency closure;
3. consumers: chain, status, watchdog, repair, publication, and human-gate
   consumers use the smallest canonical authority/operational view in their
   declared rollout mode, with remaining compatibility readers explicitly
   listed in the final migration report.

### Independent Initiative: Megaplan Maintenance

The canonical four-milestone Maintenance chain may proceed, pause, or complete
independently of WBC. WBC consumes whatever Maintenance contracts are actually
landed at the pinned launch revision and must fail visibly on incompatible
current source, but Maintenance completion and its manifest do not gate launch.

The proof map must demonstrate:

1. containment: the master mutation gate dominates L1/L2/L3; one central repair
   queue root; durable action receipts; typed `UNKNOWN`; provisional liveness;
2. coherent authority: versioned observation/detection/attempt/verification/
   audit/incident contracts, coherent or explicitly partial reads, replayable
   journal failures, occurrence identity, and `TransitionWriter` as the sole
   plan/chain lifecycle mutator;
3. independent verification: attempt is separate from terminal closure,
   blocker-specific delayed verification and reopen work, and canary/rollback
   evidence is truthful;
4. six-hour product: exact-window read-only aggregation, explicit coverage and
   unknowns, immutable inputs, reproducible hashes, and routed findings that do
   not mutate audited state.

If Run Authority changes after its manifest is written, manifest hash validation
must fail and a fresh manifest/proof map is required.

## C1 Automatic Shared-Mutation Gate

Passing chain launch preconditions permits only C1. Before C2 can mutate shared
runtime surfaces, C1 must produce all of the following in its milestone branch.
The milestone validator checks these artifacts and either advances or aborts
with stable diagnostics; no person approves the handoff:

- a source-to-owner matrix for every boundary writer, observation collector,
  decision writer, evaluator, queue writer, repair actor, status projection,
  and auditor consumer;
- a contract-to-producer matrix generated from current code, not old filenames;
- a machine-readable supported-runtime/step matrix and versioned execution-
  attempt ledger schema covering start, completion, failure, retry,
  suspension/resume, cancellation, payload/reference governance, ordering,
  atomicity, and persistence-failure behavior;
- a versioned current-runtime fixture captured from the combined prerequisite
  schemas and a redacted legacy fixture from before those schemas;
- read-only replay tests for `state.json`, history, `phase_result.json`, boundary
  receipts, execution grants/attempts/decisions/quarantine, observation and
  repair/verification events, repair requests/decisions, watchdog reports,
  status snapshots, and six-hour audit records;
- observe-only semantic evaluation with the master mutation gate and all
  dispatch flags off, proving zero lifecycle, queue, source, commit, push, or
  audited-input mutation;
- the combined prerequisite-focused regression suites green from a clean base.

C1 validation must fail and abort the chain if any required current schema is absent, a major consumer still
independently mutates from raw compatibility artifacts, a runtime fixture cannot
be replayed without normalization-by-write, or two components claim mutation
authority over the same surface.

## Ownership Matrix

| Surface | Owner | WBC role |
| --- | --- | --- |
| Capability/dispatch grants, attempts, claims, accepted decisions, quarantine, execution frontier | Run Authority | Reference decision/evidence IDs; never infer acceptance from artifact labels. |
| Runner, publication, human-gate, recovery views | Run Authority domain bindings | Declare evidence profiles and consume view outputs; do not add a competing aggregate status. |
| Coherent observations and read tearing policy | Megaplan Maintenance | Evaluate only coherent or explicitly partial/unknown envelopes. |
| Plan/chain lifecycle mutation and CAS/preconditions | Maintenance `TransitionWriter` | Declare required transition evidence and report mismatches; never mutate lifecycle directly. |
| Master/path mutation gates and central repair queue | Megaplan Maintenance | Enqueue through the canonical API only when both observation and dispatch policy allow it. |
| Repair attempt, independent verification, close/reopen custody | Megaplan Maintenance | Attach boundary/finding refs and verify contract clearance; do not add a second finding lifecycle that claims custody. |
| Status and six-hour truth semantics | Megaplan Maintenance, fed by Run Authority views | Supply typed findings/reasons; status/auditor remain projections/consumers. |
| Kernel execution-attempt ledger, boundary declarations, receipts/evidence profiles, payload/reference governance, template compatibility, semantic mismatch findings | Workflow Boundary Contracts | Canonical recording/proof owner. Reuse Run Authority attempt/decision identity and Maintenance transitions; never grant authority, mutate lifecycle, or self-clear. |
| Legacy runtime JSON | Its existing writer; classified by Run Authority as observation/claim/projection | Read through versioned adapters and fixtures; never silently promote it to authority. |

## Rebase And Launch Assumptions

- The completed Run Authority PR history is an ancestor of the launch base on `main`.
- The launch checkout is clean and uses a unique workspace, chain session, and
  log; it does not execute from the mutable shared editable source.
- The runtime source revision is pinned to the same Run-Authority-integrated `main` SHA used by
  the WBC milestone branch.
- No Run Authority chain is still mutating its milestone branches or shared
  runtime schema.
- Any post-manifest Run Authority change invalidates the launch until manifests,
  fixtures, and C1 matrices are refreshed.

## Audited Cloud Launch Contract

- Use this initiative's `cloud-config.yaml` via the CLI's explicit
  `--cloud-yaml` option. It reserves
  `/workspace/workflow-boundary-contracts-corrective-20260710/Arnold`, tmux
  session `workflow-boundary-contracts-corrective-20260710`, and the matching
  per-session log.
- Before launch, run local cloud preflight with `--skip-remote`, then run remote
  preflight. Any reported human-gated chain policy is a configuration failure;
  do not use `--allow-human-gates`.
- Confirm all six milestones resolve to `profile: partnered-5` and
  `vendor: codex`, the driver declares Codex, and the resolved Partnered-5
  planning and execution routes match the requested profile.
- Complete the already queued operational editable-install verification. Confirm
  the launcher's synced `editible-install` ref (the current configured ref name)
  and the chain base both resolve to the audited Run-Authority-integrated `main`
  SHA; record that SHA and the Run Authority manifest hash in launch evidence. This remains
  a launch blocker and this initiative does not alter the VP todo entry that
  tracks it.
- Launch through the canonical cloud chain wrapper with this exact spec and
  `--fresh`. Never invoke local `chain start`, reuse another
  initiative's workspace/session, or bypass the `chain_completed`
  precondition.

## Human-Stop Classification

No human stop remains inside C1-C6. Planning approval, milestone merge, C1
mutation-gate review, backend selection, payload policy, retention policy,
adapter selection, template re-pin, rollout advancement, human-boundary test
input, and external-effect test input all have deterministic policies or
fixtures.

Two pre-launch gates remain: content-addressed completion of Run Authority and
the already queued editable-install/base-SHA equality verification from the VP todo. They cannot be
automated away by this initiative because they attest to externally owned code
and launch-runtime identity. They are checked before chain creation and do not
interrupt C1-C6. This initiative neither edits nor satisfies the VP todo.

Production-wide dispatch, destructive provider actions, force-proceed/waiver,
and real end-user approval remain separately authorized operational actions.
They are not needed to execute or accept this epic; conformance uses
observe-only, fake, fenced, or signed-fixture inputs.
