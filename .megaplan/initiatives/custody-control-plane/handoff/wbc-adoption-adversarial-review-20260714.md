---
type: handoff
date: 2026-07-14
status: blocking-review
reviewed_run: subagent-20260714-132133-8baadfb6
source_incident: workflow-boundary-contracts-corrective-c1-to-c2-c6-handoff
---

# Adversarial review: universal WBC adoption and chain-custody drift

## Verdict

The in-progress custody-control-plane rewrite materially fixes the schema-only
and declaration-only WBC outcome. M6/M6A/M8/M9/M10/M11 now require a real
transactional store/API, production writers and readers, fail-closed or typed
indeterminate behavior, static/runtime set equality, fault/replay/migration
proof, and evidence-gated retirement of best-effort/raw-state bypasses.

It does **not yet make execution of that scope inevitable**. The proven C1
incident can recur before those milestones run: the launched chain is not
immutably bound to the current `chain.yaml`, ordered milestone/brief set,
NORTHSTAR, normalized remote copy, source revision, and installed runtime. A
later M6 or M11 validation cannot protect a chain controller that silently
advances from M5 into an older successor sequence and therefore never runs the
validation milestone.

This review is deliberately a separate handoff. It does not overwrite the
active owner's initiative edits and does not authorize launch, resume,
reconcile, install, deployment, restart, or merge.

## Proven recurrence path

The completed root-cause evidence in resident run
`subagent-20260714-132228-8ec58f5c` establishes:

- corrective C1 ran with NORTHSTAR hash `e6168abb...` and a corrective C1-C6
  chain hash `1c7336d4...`;
- active chain custody retained old S1-S4 hash `6b9516d6...`;
- C1 was recorded as old `s1-operational-semantic-health`, so the controller
  created old S2 and skipped corrective C2-C6; and
- C2-C6, not C1, owned durable append/query, real producer/consumer migration,
  fail-closed persistence, legacy retirement, and universal proof.

Current source still permits the same class:

- `cloud/cli.py::_chain_identity_for` hashes only slug, optional seed, and
  milestone labels; it is not a content hash of the executable bundle.
- `_cloud_chain_launch_provenance` records milestone count/current label and
  runtime hints, but not immutable local/remote chain, NORTHSTAR, brief, and
  runtime digests as one accepted launch receipt.
- `chain/spec.py::save_chain_state` rewrites `metadata.chain_spec_sha256` from
  the **current** spec on every save. This destroys the distinction between the
  launch-bound hash and later observed bytes.
- `supervisor/chain_runner.py::run_chain` loads the current spec and persisted
  cursor but performs no comparison to an immutable launch bundle before the
  first milestone or each handoff.
- `chain/operator_pause.py::resume_chain` restores state without checking a
  launch-bound spec/NORTHSTAR/brief/runtime identity.
- prerequisite completion manifests validate a completed prerequisite against
  its current spec, but that does not bind this chain's own execution identity.

## Blocking correction 1: immutable chain execution binding

Before this epic is launchable, land and test a generic chain-control guard
outside the later milestone sequence. Record one immutable launch receipt
before the first plan is initialized containing at least:

- canonical local `chain.yaml` path and SHA-256;
- normalized uploaded remote spec path and SHA-256, with byte/semantic equality
  to the accepted local source transformation;
- ordered milestone labels, indices, brief paths and brief SHA-256 values;
- top-level and milestone NORTHSTAR paths, identities, and SHA-256 values;
- source commit/tree, dirty-diff digest, base/target refs, and workspace/session
  identity;
- engine source revision, import-resolved editable/install revision and module
  path, package/wrapper/config/template/schema digests, and running process
  provenance; and
- an explicit expected next milestone and predecessor receipt at each handoff.

Keep `launched_*` fields immutable. Store later `observed_*` fields separately;
never update launch identity during an ordinary state save. Launch, milestone
advance, pause/resume, restart, repair/relaunch, and reconciliation must
recompute observed identity and reject on any mismatch with a typed
`CHAIN_EXECUTION_BINDING_DRIFT` result. A rebind must be an explicit,
content-addressed, operator-authorized migration event, never normalization or
implicit adoption of current files.

Status/introspect/cloud views must show expected versus observed chain hash,
NORTHSTAR hash, milestone sequence/index, active plan binding, source revision,
and runtime revision. Unknown or disagreement is action-off, not a warning.

Required regression fixture: recreate the WBC incident exactly--a plan anchored
to corrective C1/NORTHSTAR while persisted chain custody retains old S1-S4--and
prove launch/handoff/resume/reconcile all stop before old S2 is initialized.
Also mutate only a later brief, reorder successors without changing the current
label, alter the normalized remote spec, and change the editable import target;
each must fail closed.

Because M5 is already part of the chain being protected, this guard is an
external prelaunch dependency. Assigning it only to M8/M10/M11 is circular and
does not prevent another skipped handoff.

## Blocking correction 2: cumulative NORTHSTAR acceptance

Every milestone, not only M11, needs a cumulative initiative acceptance
receipt. Before marking milestone N complete or initializing N+1, recompute the
immutable execution binding and prove:

1. the finalized plan and review used the expected milestone brief and anchor;
2. all predecessor handoffs and previously satisfied NORTHSTAR obligations
   remain satisfied against current source/runtime evidence;
3. the milestone's matrix rows moved only through machine-derived evidence;
4. no previously conformant writer/reader/negative test regressed; and
5. blocking suites ran in enforce mode--no shadow baseline, nominal manifest,
   declaration, or plan-local green review can close the gate.

The cumulative receipt must be a required input to chain advancement and the
final completion manifest. This directly addresses the old S2-S4 reviews that
passed their local declaration/projection tasks while the initiative's durable
writer/reader end state remained absent.

## Major correction 3: make the boundary inventory an independent oracle

`research/wbc-boundary-adoption-matrix.md` is currently a good family-level
contract, but it is not itself a complete leaf inventory. M6 defers the exact
rows to a future generated JSON. To keep generation from reproducing the
candidate support-manifest false positive, M6 must deliver the generator,
versioned discovery rules, committed machine-readable rows, and CI acceptance--
not only the generated output.

Seed and reconcile exact path/symbol leaves from the completed producer and
consumer audits, including common phase workers, provider/process attempts,
tiebreaker, feedback, review/finalize, fanout/reducers, chain/epic/bakeoff and
publication, resident roots/children/scheduler/outboxes, cloud/AgentBox,
watchdog/L1/L2/L3/auditor, pause/resume/cancel/retry/replay, retention/migration,
and shell wrappers. Use at least two independent discovery channels (static
Python/native/wrapper discovery and captured runtime traces) plus declared WBC
contracts. Dynamic/generated/native/shell/external surfaces must not disappear
merely because an AST scanner cannot see them. The equality equation must expose
each unmatched set separately and default deny every exclusion.

Historical adapters require a machine-readable allowlist containing exact
path/symbol, read operations, supported versions, proof of zero
authority-increasing callers, owner, approval, expiry, and deletion gate.
`approved adapter` without that record is ambiguous.

## Major correction 4: separate base contract identity from implementation identity

M6 correctly pins the final landed WBC contract candidate, while M6A is expected
to add storage, uniqueness, terminal-order enforcement, process-safe APIs, and
migrations that the candidate does not contain. Those changes may require a
compatible WBC contract revision rather than merely an adopter implementation.
The initiative must explicitly distinguish:

- the audited/landed WBC base contract revision;
- the approved WBC-owned substrate/API revision produced by M6A;
- each adopter source revision; and
- the installed/editable/cloud/resident runtime vector that executes them.

If M6A requires schema/contract changes, obtain an explicit WBC-owner handoff
and regenerate conformance/support evidence. Otherwise fail closed rather than
quietly changing a supposedly pinned prerequisite under Custody ownership.
Later milestones must bind the evolving implementation vector while preserving
the immutable base-contract lineage.

## Acceptance disposition

The universal writer/reader, fail-closed authority, legacy quarantine, runtime
trace, migration, and end-to-end conformance clauses are directionally
sufficient once made executable. The epic remains **not launch-ready** until
the immutable self-chain binding, launch/resume/reconcile drift guard, and
cumulative NORTHSTAR handoff gate exist and are verified outside the chain they
protect. Missing final WBC merge identity and unresolved installed/runtime
identity remain legitimate hard gates.

## Verification performed

- Parsed the current `chain.yaml`, verified nine unique ordered milestone
  labels, and resolved every referenced brief.
- Inspected the target manifest, live log, all three completed child results,
  the current initiative assets, WBC candidate/source worktrees, and completed
  C2-C6 root-cause artifact.
- Ran a temporary source diagnostic against
  `cloud/cli.py::_chain_identity_for` and `chain/spec.py::save_chain_state`:
  mutating executable spec content without changing labels kept the launch
  identity unchanged, while the next ordinary state save replaced
  `chain_spec_sha256` and retained no immutable `launched_*` binding.
- `git diff --check -- .megaplan/initiatives/custody-control-plane` passed.
- Focused pause/resume tests currently report 2 passed and 1 unrelated
  dirty-tree failure: the implementation adds repair-environment `tmux -e`
  arguments while `test_cloud_session_pause_stops_only_owned_runner_and_repair`
  still expects the older command. No concurrent runtime/test code was changed
  by this review.

## Concurrent correction status

While this review was running, the canonical initiative added the external
guard contract, cumulative North Star receipt, separate WBC base/substrate/
adopter/runtime identities, independent inventory generator/CI artifacts, and
a deliberately missing prelaunch receipt. Canonical `validate_paths()` now
fails closed at the absent
`evidence/chain-execution-binding-receipt.json`, so the chain remains
unlaunchable as intended.

The current `chain.yaml` check is only `contains_text` for the receipt schema
name. That is a sentinel, not proof: a hand-authored or stale file containing
the string would satisfy the existing generic artifact check. The external
guard must therefore be wired into launch/handoff/resume/reconcile as an actual
receipt validator that recomputes and compares every bound digest. Until the
chain precondition supports that validator (or invokes a content-verifying
command/receipt kind), receipt presence must never be described as sufficient
admission authority.

The target owner's combined validation run is not green: 54 tests passed and 3
failed. One failure is directly authority-relevant:
`test_auto_merge_waits_for_merged_pr_before_appending_completion` observed
`done` where `awaiting_pr_merge` was required. Two resident hot-context tests
lost the expected `epic_chains`/`active_chains` projection keys. These may be
concurrent dirty-tree regressions rather than initiative-doc defects, but they
must remain explicit base-health blockers/caveats; no completion or launch proof
may describe the current source/runtime suite as fully passing. The auto-merge
failure belongs in the generic chain-binding/cumulative-acceptance regression
set because premature completion can bypass a handoff even when hashes match.
