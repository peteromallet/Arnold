# Workflow Boundary Contracts

This initiative is a six-milestone corrective epic for making declared workflow
boundaries agree with durable runtime reality. It is deliberately launch-blocked
until Run Authority has completed, landed, and supplied current authoritative
completion evidence. Megaplan Maintenance is adjacent work, not a launch gate.

The corrective chain consumes, rather than competes with, the owned surfaces it
finds at its pinned launch revision:

- Run Authority owns grants, accepted attempts, decisions, quarantine, execution
  authority, and the runner/publication/human-gate/recovery views.
- Megaplan Maintenance owns coherent observations, the lifecycle
  `TransitionWriter`, mutation gates, repair-attempt and independent-verification
  custody, status truth semantics, and the exact-window six-hour product.
- Workflow Boundary Contracts owns declarations of expected boundary effects,
  the kernel execution-attempt ledger and its evidence/payload reference
  contract, receipts/evidence that satisfy declarations, compatibility
  profiles, and semantic findings produced by comparing declarations with
  authoritative observations and decisions. The ledger records execution; it
  does not replace Run Authority decisions or Maintenance lifecycle mutation.

## Supported Workflow Surfaces

The epic's universal guarantee applies to every step and attempt executed by
the supported `arnold.workflow` runtime and its Megaplan adapters: prep,
plan/revise, critique/gate/tiebreaker/reducer, finalize, execute, feedback,
review, human suspension/resume, chain and publication steps, cloud repair and
verification work, and auditor workflow steps. C6 also makes the selected
native Python-shaped runtime adapter a required adopter, not an optional demo.

Manual work performed wholly outside a supported runtime, third-party systems'
internal execution, and historical read-only runs are out of scope. A supported
step's calls into those systems are still ledgered as external-effect intents
and outcomes. Compatibility readers may be time-bounded during C1-C5, but no
supported producer may remain exempt at final acceptance.

## Launch Gates

`chain.yaml` enforces one content-addressed initiative precondition:

1. the complete three-milestone Run Authority chain must be landed on `main` and
   have a matching `completion-manifest.json`.

The manifests must hash the current chain, North Star, milestone briefs, chain
state, merge evidence, and deliberate proof artifacts. Merely observing a
terminal status, merged first milestone, live process, or green PR is not enough.
The exact proof and ownership checks are recorded in
`notes/launch-gates-and-ownership.md`.

Do not launch from the current detached/dirty shared checkout. Launch only from
a clean checkout containing the completed Run Authority result, with a unique
workspace/session/log and a pinned editable runtime source revision.

## Unattended Execution Configuration

Every executable milestone uses the `partnered-5` profile and explicitly
declares `vendor: codex`; the chain driver is also pinned to Codex. The profile
covers prep, plan, critique/evaluation, revise, gate,
finalize, execute, feedback, review, and tiebreaker phases without a non-Codex
fallback.

`cloud-config.yaml` reserves an initiative-specific workspace, tmux session,
and log. `merge_policy: auto`, `driver.auto_approve: true`, and
`prep_clarify: false` make milestone planning, approval, clean-PR merge, and
advancement non-interactive. C1-to-C2 is a machine-validated mutation gate: a
failed invariant aborts the chain with evidence; it does not request an
operator verdict. The frozen execution defaults and automatic selection rules
are recorded in
`decisions/2026-07-11-unattended-execution-defaults.md`.

## Corrective Milestones

| Milestone | Outcome | Mutation class |
| --- | --- | --- |
| C1 | Reconcile declared contracts with actual producers and freeze legacy/current compatibility fixtures. | Read-only inspection and boundary-local fixtures only. |
| C2 | Implement the kernel execution-attempt ledger, durable findings, and failure-visible persistence semantics. | First shared-surface mutation; blocked until C1 evidence passes. |
| C3 | Migrate all supported Megaplan phase/reducer/cloud execution seams and shared consumers to the ledger. | Shared producers/consumers; shadow first, then required. |
| C4 | Migrate chain, PR/publication, repair, verification, and auditor attempts and external effects. | Authority/effect integrations over existing owners. |
| C5 | Complete payload/reference, retention/security, template, and authority-adapter integration. | Public schema and governance surface; no alternate mutator. |
| C6 | Make the pinned `arnold.pipeline.native` adapter a required adopter and prove universal query/replay/audit/conformance. | Final gate: zero undeclared supported-surface gaps. |

The previous four sprint briefs and detailed `m1` through `m10` briefs remain in
place as historical research/checklists. They are superseded as executable
milestones by the C1-C6 briefs; useful acceptance details must be reconciled,
not copied blindly.

## Failure Policy

Every milestone fails closed and `stop_chain` records the violated criterion
when prerequisite contracts are missing, contradictory, or still have more
than one mutating owner. These are automated failure outcomes, not mid-chain
questions or approval pauses. No milestone
may weaken a Run Authority or Maintenance guard, hand-edit lifecycle state as a
repair strategy, create a second repair queue/status enum/custody lifecycle, or
treat compatibility JSON as new authority.

No success path may swallow a ledger persistence failure. Hashes prove identity
or integrity only; they do not preserve inputs, results, artifacts, verdicts,
state deltas, or external-effect evidence without a durable retrievable object.

The epic does not authorize production-wide dispatch, destructive external
effects, force-proceed, or real human approvals. Implementation and conformance
use shadow/read-only paths, fakes, fixtures, or already-authorized prerequisite
interfaces. Any later production enablement remains an external operational
safety decision and is not a condition for C1-C6 completion.
