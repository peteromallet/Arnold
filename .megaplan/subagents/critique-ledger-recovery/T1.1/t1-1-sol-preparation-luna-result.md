# T1.1 Sol preparation — raw-evidence CL2 admission and one-successor CAS

Status: **read-only preparation only**. T1.1 is not implemented or complete.
No code, worktree, cloud/provider state, incident state, or owner decision was
mutated. The only write is this report.

## Baseline and governing contract

- Exact clean recovery ancestor: `6787d6363e8fc0603092913ae877db14f3b9fff8`
  (`Use GPT-5.6 Sol for GLM profile finalization`). All source claims below were
  checked with `git show`/`git grep` against that commit, not the dirty main
  checkout.
- Governing source:
  `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
- T1.1 owner: Megaplan domain plus Run Authority. Authorization is repo-only
  `DEV-PR`; there is no cloud promotion in T1.
- Direct dependency: T0.2 only. Downstream edges are T1.4; T2.2 depends on all
  T1.1–T1.10; authoritative fresh-handoff T5.2 depends on T1.1, T1.3, T3.6,
  and T5.1.
- Required behavior: versioned, allowlisted, target-bound derivation from raw
  hashed CL1 evidence; re-evaluate under fence immediately before plan creation;
  false/missing/stale/wrong-target/unknown/throwing rejects; `auto_approve`
  cannot absorb it; two installed initializers converge to one successor.
- Named minimum tests are exactly:
  `test_initial_cl2_admission_rejects_false_handoff_with_auto_approve`,
  `test_admission_recomputes_raw_evidence_not_stored_true_boolean`,
  `test_admission_rejects_stale_wrong_target_missing_and_throwing_predicate`,
  `test_admission_rereads_under_fence_before_plan_creation`, and
  `test_two_initializers_cas_to_one_successor`.

## Finding: there is no current CL2 admission boundary

The incident was not a subtle predicate bug. The domain predicate was never an
input to the generic chain authority path.

| Surface at `6787d636` | What it proves | Why it cannot admit CL2 |
| --- | --- | --- |
| `arnold_pipelines/megaplan/chain/source_admission.py::admit_milestone_source` | Current milestone brief exists and its semantic hash matches an execution binding or explicitly registered replacement | No CL1 schema, raw evidence, predicate allowlist, target tuple, freshness, owner decision, Run Authority view, or atomic initialization |
| `arnold_pipelines/megaplan/custody/admission_control.py::validate_admission_mutation` | A statically registered writer supplied a source-shaped record and its in-memory fence booleans were true | Returns evidence only; it owns no durable revision, lock, grant, fence, decision, or CAS |
| `arnold_pipelines/megaplan/chain/spec.py::validate_launch_preconditions` | Generic `exists`, `contains_text`, `review_log_clean`, `git_tracked`, or prior-chain-complete checks | Launch-time only, string/file shaped, not per-milestone raw derivation and not reread at successor creation |
| `arnold_pipelines/megaplan/chain/epic_chain.py::_verify_handoff` | Handoff file exists/contains text and optionally predecessor PR is merged | A stored `accepted_for_cl2=true` string would pass; no derivation or target binding |
| `arnold_pipelines/run_authority/{contracts,reducer,current_source}.py` | Immutable generic record shapes and a pure reduction/evaluation over records already supplied by a caller | No durable owner reader/writer/store, no reservation operation, and no CAS that can issue one successor |

The v2 initiative reinforces the gap:

- `.megaplan/initiatives/critique-ledger/chain.yaml` declares only serial
  `depends_on: cl1-contract-oracle` for CL2. `MilestoneSpec` has no machine
  prerequisite field.
- The CL1 brief requires
  `docs/critique-ledger/handoffs/cl1-contract-oracle.json` and says CL2 must
  reject missing/stale/unreviewed/blocker-bearing handoffs, but that handoff is
  absent from commit `6787d636`.
- The clean-ancestor chain has `driver.auto_approve: false`; the captured
  incident plan state had `auto_approve: true`. Neither value matters to a
  machine prerequisite today because no such prerequisite is consumed.

## Exact initializer and bypass paths

There are two chain initializers, one shared weak plan constructor, and several
wrappers that ultimately select one of the two:

1. Default/legacy installed path:
   `python -P -m arnold_pipelines.megaplan chain start` →
   `chain/__init__.py::run_chain_cli` → `chain/__init__.py::run_chain` →
   `_init_plan`. This path does **not** call `admit_milestone_source`.
2. Flagged supervisor path: the same installed command with
   `MEGAPLAN_SUPERVISOR_TIER=1` →
   `supervisor/chain_runner.py::run_chain` →
   `_admit_chain_materialization` → `ChainMilestonePackRunner.prepare_plan` →
   the same `_init_plan`. Its admission is source identity plus two in-memory
   booleans (`current_milestone_index`, `current_plan_name is None`), followed
   by a non-CAS state save.
3. `chain/__init__.py::run_chain_cli` selects (1) unless
   `feature_flags.py::supervisor_tier_routing_on()` sees the exact environment
   value `1`. An environment flag therefore selects the weaker path.
4. `cloud/cli.py::_chain_start_command`, cloud supervision/relaunch, and
   `epic_chain.py::_default_start_child_chain` all spawn the installed
   `python -P -m arnold_pipelines.megaplan chain start`; they inherit this
   split and its default legacy bypass.
5. `_init_plan` spawns installed
   `python -P -m arnold_pipelines.megaplan init --idea-file ...` without
   `--name`. `handlers/init.py::handle_init` creates a timestamp-derived name,
   checks `plan_dir.exists()`, records generic custody evidence, then calls
   `mkdir`. It has no chain/CL1/Run Authority receipt.
6. `control.py` sprint initialization and
   `cloud/m11_workflow_canary_runner.py` call `handle_init` directly. They are
   legitimate non-chain consumers that a shared-handler change must preserve;
   they must not silently acquire CL2 authority.
7. `pyproject.toml` exposes no `megaplan` console script. The actual installed
   surface is module execution through `arnold_pipelines/megaplan/__main__.py`;
   testing only direct Python functions is insufficient.

Direct standalone `init` may remain a generic plan tool, but a directory it
creates without a chain admission receipt must never be adoptable as a chain
successor. Every chain-owned invocation must carry and consume the owner receipt.

## Why the current persistence/CAS surfaces are unsafe

- `ChainState` has no revision/CAS cursor. `save_chain_state` writes a fixed
  `.tmp` and replaces the authority file. Its M7 projection append occurs
  afterward and every projection error is explicitly non-fatal. Two readers can
  both observe `current_plan_name=None`, create plans, and last-writer-win.
- `handlers/init.py`'s `plan_dir.exists()` fence is a local precheck, not an
  owner reservation. Timestamp names make the contenders likely to create two
  different plans; equal names merely turn the loser into `duplicate_plan`
  without proving which plan Run Authority accepted.
- `_core/io.py::commit_journal_transaction_cas` evaluates filesystem hash/
  absence guards and only then calls the commit routine, with no interprocess
  lock around the read-then-write interval. Existing
  `test_journal_cas.py` and `test_acceptance_transaction_cas.py` inject a stale
  sequential mutation; they do not prove simultaneous contenders. This helper
  must not be relabeled as the T1.1 authority CAS.
- Completion acceptance in `orchestration/completion_io.py` is a different,
  later boundary. It cannot reserve initial successor creation.
- At the ancestor, Run Authority has a pure reducer, not a store. Also,
  `CurrentSourceRequest.fence_token` is typed `str` while
  `CoordinatorFence.token`/grant tokens are `int`; exact evaluation compares
  them directly. Do not build T1.1 atop this interface without correcting and
  regression-testing that mismatch.
- Later RA-CONTAIN work is not in `6787d636` and solves issue/terminate
  containment, not CL2 admission. Keep T1.1 disjoint from
  `run_authority/containment.py`; only a small export integration may overlap.

## T0.2 evidence boundary

T0.2 is valid preserved incident evidence, not current positive authority:

- `evidence/critique-ledger-recovery/T0.2/manifest.json` records 319 claims and
  230 unique content-addressed objects; its verifier receipt is the accepted
  T0.2 boundary.
- It preserves the v2 chain/brief objects and incident plan records showing the
  unaccepted handoff problem, including the blocking clarification and later
  unsafe assumption.
- It contains **zero** manifest claims whose logical name is
  `docs/critique-ledger/handoffs/cl1-contract-oracle.json`; the canonical
  handoff itself was not captured as a current owner record.
- T0.4 explicitly records: “no persisted Run Authority owner ledger” and
  `owner_record_path_or_uri: UNAVAILABLE` for grants/decisions/fences.

Therefore T1.1 can use T0.2 as immutable negative/offline fixtures and can
implement the mechanism, but it cannot infer a fresh accepted CL1 decision from
historical excerpts. T5.1 must resolve the reviewer/coherence/proof/ownership/
portfolio blockers, and T5.2 must generate and independently recompute the
fresh target-bound handoff through the new mechanism.

## Missing owner contracts that must be explicit

### Megaplan/CL1 predicate contract

Define one versioned, closed-schema prerequisite declaration per milestone:

- allowlisted predicate id and deriver version;
- exact raw evidence object set and canonical byte/hash algorithm;
- manifest and independent verification-receipt digests;
- exact target tuple: initiative/spec hash, milestone label/index, predecessor
  subject/revision, intended successor run/revision/plan identity, source base,
  runtime generation, workspace/session and expiry/freshness basis where used;
- domain rules for reviewer status, M6 coherence, proof result, ownership
  blockers, portfolio approval, amendments, and zero open blockers;
- outcome algebra `SATISFIED | REJECTED | UNKNOWN`, where every parse/schema/
  I/O/unknown-version/extra-field/duplicate/wrong-target/stale/throwing case is
  non-satisfied with typed reasons;
- predicate digest over canonical raw inputs and target, never over the stored
  `accepted_for_cl2.value` projection.

The handoff may cache the derived boolean for display, but admission must
recompute and require byte-for-byte agreement with its proof; disagreement
rejects.

### Run Authority reservation contract

Run Authority needs a durable owner API, not a Megaplan evidence record:

- authoritative current-view read plus exact revision/fence CAS;
- idempotency key over `(run, revision, milestone target, predicate digest,
  deterministic successor identity, intent)`;
- capability/grant scope for exactly `reserve_successor` and
  `materialize_successor`, with coordinator attempt and fence token;
- durable reservation states such as `RESERVED`, `MATERIALIZED`, `ABORTED`, and
  `INDETERMINATE`, plus queryable receipt and conflict reasons;
- same-payload retry returns the exact committed receipt; same key with a
  different target/evidence/intent conflicts; stale revision/fence denies;
- crash/ack-loss recovery proves the authoritative owner record before retry;
  it never guesses from a plan directory or projection;
- one owner transaction chooses the deterministic plan identity before any
  directory/process/provider effect. A second initializer either joins the
  exact reservation or loses; it never creates another plan;
- materialization consumes that receipt immediately before `mkdir`, rereads
  the immutable evidence hashes/current owner pointer under the same fence, and
  records an admission marker in the new plan. An existing directory is adopted
  only if its receipt/identity bytes exactly match the owner record.

A local reference store may use SQLite `BEGIN IMMEDIATE` plus unique keys and
revision predicates to prove two-process behavior. It must be visibly a test/
local implementation unless the Run Authority owner accepts it as production;
ordinary filesystem check-then-replace is not sufficient.

## Recommended bounded mutation scope

Keep policy, authority, and orchestration separate:

1. Add persistence-neutral admission/reservation records and a durable owner
   port under `arnold_pipelines/run_authority/` (for example
   `admission.py` plus an explicitly selected store/adapter). Do not put CL1
   policy or containment behavior there.
2. Extend `chain/spec.py` with a closed, versioned per-milestone
   `machine_prerequisites` declaration. Reject unknown predicate ids/versions
   and unknown fields while loading the spec.
3. Add a Megaplan adapter (for example
   `chain/prerequisite_admission.py`) that hashes/rereads raw objects, runs the
   allowlisted CL1 deriver, constructs the target tuple, and asks Run Authority
   to reserve the deterministic successor.
4. Make **both** `chain/__init__.py` and
   `supervisor/chain_runner.py` call one shared `admit_and_reserve_successor`
   function. Do not duplicate logic and do not place the invariant behind
   `MEGAPLAN_SUPERVISOR_TIER`.
5. Change `_init_plan` to accept the preallocated plan name and admission
   receipt and pass the exact `--name` plus a typed receipt reference to the
   installed module entrypoint. Chain callers may not omit them.
6. In `handlers/init.py`, verify/consume the reservation immediately before
   plan directory creation for chain-owned init; preserve explicit standalone,
   sprint-control, and canary modes without allowing their output to be adopted
   as a chain successor.
7. Do not mutate the poisoned v2 chain/spec/artifacts to manufacture a pass.
   Exercise generic test specs now; T5.3 later commits the fresh v3 spec using
   the new declaration after T5.1/T5.2 owner work.

Likely changed production files:

- `arnold_pipelines/run_authority/{contracts.py,__init__.py}` plus new admission
  contract/store module(s);
- `arnold_pipelines/megaplan/chain/{spec.py,__init__.py}` plus a new prerequisite
  adapter;
- `arnold_pipelines/megaplan/supervisor/chain_runner.py`;
- `arnold_pipelines/megaplan/handlers/init.py`;
- CLI parser/projection files only as required to carry an opaque typed receipt.

Avoid broad changes to cloud launchers: once the installed `chain start`
boundary is invariant, cloud and epic-chain inherit it. Add static/installed
tests proving that fact instead of another cloud-specific policy implementation.

## Exact verification attack surface

Add focused suites, while retaining the five required names:

- `tests/arnold_pipelines/megaplan/test_cl2_raw_evidence_admission.py`: true,
  false, stored-true/raw-false disagreement, missing, corrupt, stale,
  wrong-target, unknown version/id, extra fields, throwing deriver, auto-approve,
  and reread-after-first-check cases; assert no plan directory/model subprocess.
- `tests/arnold_pipelines/run_authority/test_admission_reservation.py`: exact
  idempotent replay, conflicting replay, stale fence/revision, crash/ack loss,
  and real two-thread plus two-process contention yielding one reservation and
  one deterministic plan.
- `tests/arnold_pipelines/megaplan/test_cl2_admission_installed_cli.py`: invoke
  `python -P -m arnold_pipelines.megaplan chain start` in both supervisor flag
  states, retry/resume/fresh paths, and an epic-chain child; prove identical
  fail-closed behavior and exactly one accepted successor.
- Extend `test_canonical_source_admission.py` only for coexistence with source
  identity; do not pretend its present tests cover CL1.
- Extend `test_chain_launch_preconditions.py`, `test_epic_chain.py`, and
  `test_chain_worktree_safety.py` for bypass/non-adoption assertions.
- Run existing `test_journal_cas.py` and
  `test_acceptance_transaction_cas.py` as regression only, not T1.1 proof.
- Run `tests/arnold_pipelines/run_authority/{test_contracts.py,test_reducer.py}`,
  `tests/run_authority/test_dependency_closure.py`, the focused Megaplan chain
  suites, and wheel/installed-package smoke. The installed test must build and
  run outside checkout/PYTHONPATH authority.

Formal T1.1 completion still requires an independent review plus accepted
owner/integration evidence under `E/T1.1/`; a green local implementation alone
must not be projected as deployed authority or as a resolved CL1 handoff.
