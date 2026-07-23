# Custody M9/M10 runtime-fix consolidation and cutover plan

Date: 2026-07-23  
Status: candidate assembled; integrated validation in progress  
Canonical integration branch: `integrate/custody-m10-runtime-convergence-20260723`

## Decision

The M9/M10 incident fixes must be consolidated as source before the live engine
is changed. Whole repair branches must not be merged: they contain divergent
resident history and conflict with the M9 projection/WBC contract. Each
still-relevant behavior is transplanted semantically, with an incident
regression and a source-SHA-to-destination-SHA ledger.

The current M10 chain is paused at a safe invocation boundary: state `blocked`,
phase `gate`, no active step, no model/execute worker, and the old supervisor
stopped. This boundary is safe to hold, but it is not itself permission to
activate an unvalidated candidate.

The source and runtime decisions are deliberately separate:

1. Port and review the fixes on the canonical integration branch now.
2. Publish one clean, immutable candidate commit and construct a fresh runtime
   and virtual environment from that exact advertised commit.
3. Switch only after cross-layer provenance, replay, rollback, and canary gates
   pass.
4. Resume the existing M10 gate from its durable cursor. Do not restart M10 from
   scratch and do not initialize M11 until the resumed M10 reaches durable
   execution/acceptance.

## Current landscape

| Source | State | Decision |
|---|---|---|
| M9 project branch `b21d5090a1` | Clean and pushed | Canonical project/source base. |
| Live self-host runtime `aeeffea8ba` | Clean; archived on GitHub | Keep both commits: accepted reused-batch receipt selection (`6633d792c5`) and CASExpectation reducer compatibility (`aeeffea8ba`). |
| Gate-contract fix `75aac0380c` | Clean; archived on GitHub | Integrate. It makes the prompt request every strict-schema field and keeps validation fail-closed. |
| Overnight repair line `88327293ba..8ec28d6853` | Clean; archived on GitHub | Semantic port in order; do not merge its whole ancestry. |
| Old receipt fix `3978c099ef` | Cloud-only source preserved in a bundle | Drop as duplicate: its stable patch ID is identical to `6633d792c5`. |
| Older engine/runtime line ending at `92aee9982b` | Preserved in a bundle | Port the still-missing runtime-pin, stale-gate, fallback, dirty-checkout, and narrow ITERATE-replan invariants. |
| Resident `/workspace/arnold` recent fixes | Committed source preserved in a bundle; checkout itself is dirty | Port only the custody/epoch/pause/repair invariants listed below. Do not port the dirty staged rollbacks. |
| Supervisor line ending `bc3f6a9031` | Clean committed source preserved in a bundle | Port the false chain-stuck projection fix; older branch history is already absorbed or superseded unless the port ledger proves otherwise. |
| Dirty L1 custody worktree | Five modified files, uncommitted | Port its unique prompt/profile/cursor contract and test; its blocked-task helper is superseded by `88327293ba`. Preserve until the port is proven. |
| Dirty first-task worktree | Three modified files, uncommitted | Port canonical ambiguous `CF-*` reference handling and tests. Keep force-proceed/accepted-tradeoff work out of M10 because M10 explicitly excludes force-proceed. |
| Historical dirty M5/M6 worktrees | Old, uncommitted | Evidence/fingerprint only unless a missing behavior is positively demonstrated. No deletion until explicit approval. |
| Local Mac `main` checkout | Heavily dirty and divergent | Never use as the integration source. Preserve as a separate cleanup item. |

## Port ledger

Every row requires a destination commit, focused test, and supersession verdict
before release. A blank destination means implementation is still in flight.

| Source | Behavior | Destination | Verdict / proof |
|---|---|---|---|
| `6633d792c5` | Prefer the accepted reused-batch receipt by accepted-attempt chronology | inherited in base | Kept; fixes the live M9 receipt incident. |
| `aeeffea8ba` | Exclude `CASExpectation` from authority reduction | inherited in base | Kept; focused reducer regression exists. |
| `75aac0380c` | Complete strict gate prompt contract | `75aac0380c` | Kept; 242 focused/adjacent tests passed. |
| `88327293ba` | Preserve immutable V1/V2 repair blocker identity and claimability | `85de91eb1e` | Semantically ported first. |
| `86f7c67cd6` | Preserve request/profile custody and expose recurrence to L2/L3 | `d580f88487` | Semantically ported after `883`. |
| `c834772e15` | Bind terminal repair evidence cursor | `2a70cc8562` | Ported after `86`. |
| `c18f574b8d` | Bind recovery to pinned marker/runtime/profile/no-push relaunch | `7404747f9f` | Kept binding behavior; its intermediate quality-flow behavior is superseded by `8a3`. |
| `fd1f18661b` | Bounded, deduplicated pinned recovery observation | `2c6b133aef` | Ported after `c18`. |
| `8a3d820bb4` | Resolve receipted quality blockers before recover/relaunch | `813e06e48f` | Enforces resolve → recover-blocked → pinned restart. |
| `8ec28d6853` | Use the active repair phase before external PR/CI guard classification | `f4ed215300` | Ported last in the overnight stack. |
| `3978c099ef` | Reused-batch receipt preference | none | Superseded: exact patch-ID duplicate of `6633d792c5`. |
| `db0a5d7017` | Anchor child runtime to the pinned engine | `103489711a` | Ported. |
| `97df7a0524` | Preserve pinned engine isolation across native resume | `43d2908784` | Ported. |
| `6d4f15732f` | Reject stale gate recovery after replan | `6f0bede795` | Ported. |
| `f7f096701a` | Advance a safe, side-effect-free tiered execute fallback | `6edec0e966` | Ported behind the M8 repair-adoption/validation guard. |
| `be0fea686c` | Do not reset a dirty checkout during operator resume | `acbbf5cf67` | Ported. |
| `92aee9982b` | Permit replan only for a blocked ITERATE gate | `bcbfc220e5` | Ported; supersedes broad `b5ab653e7b`. |
| `b1572e4f28` | Bind taskless repair occurrences | `4729ba0978` | Ported against the current V2 identity contract. |
| `a6acc853ed` | Dispatch exact phase failures even when classification is unknown | `71d82a538c` | Ported fail-closed. |
| `85c596f6b1` | Preserve repair prompt guard literals without unconditional push language | `cfe7c90fcf` | Ported; `8652428492` remained excluded as superseded. |
| `0ab3fbdeb7` | Reconcile an operator-pause race | `6122214ee8` | Ported. |
| `c4f72e727a` | Resume pause authority without an uncontrolled relaunch | `075cd05c66` | Ported. |
| `cf64f1e470` | Keep authority-only resume fail-closed | `a56ea086c1` | Ported. |
| `858dfb0c95` | Invalidate stale replan feasibility | `ab72303d85` | Ported. |
| `029795b157` | Bind receipts to the current plan epoch | `18f45efdee` | Ported. |
| `bc3f6a9031` | Avoid false chain-stuck watchdog projection | `3c74a9a1f0` | Ported. |
| dirty L1 payload | Preserve configured profile/cursor/success contract in repair prompts | `a0baf46ee8` | Unique policy and regression ported; superseded helper excluded. |
| dirty first-task payload | Canonicalize ambiguous `CF-*` references | `e9de12442d` | Ported with tests; force-proceed registry mutation excluded. |
| new convergence work | Guard runtime provenance, binding, marker CAS, supervisor receipts, and worker preflight | `f79df6a5b6` | New structural fix required for a safe A→B/B→A cutover. |
| convergence conflict follow-up | Preserve the profile/cursor/success contract in the active bounded repair prompt | `817ec9c328` | Prevents the contract from surviving only in a retained legacy prompt after semantic merge. |

Explicit exclusions:

- `b5ab653e7b` broad blocked replan: superseded by the narrower
  blocked-ITERATE contract in `92aee9982b`.
- `44fa8c9e24` claimable request custody: superseded by the
  `88327293ba`/`86f7c67cd6` implementation.
- `1f0b143d8e` Discord-service exclusion and the current dirty reversals in
  `/workspace/arnold`: not part of this runtime convergence.
- Force-proceed/accepted-tradeoff registry mutation: contrary to the M10 brief.
- Historical docs, raw run outputs, hardlinks, wrapper snapshots, and the M9
  `execution_batch_22.json` hardlink workaround: evidence only, never source.

## Integration order

1. Preserve every cloud-only committed line as a bundle and advertised archive
   ref before editing.
2. Start from clean `aeeffea8ba`.
3. Integrate the gate-contract fix.
4. Integrate the overnight stack in its causal order:
   `883 → 86 → c834 → c18 → fd1 → 8a3 → 8ec`.
5. Integrate older runtime/gate/pause/epoch fixes in small coherent commits.
6. Integrate only the unique pieces of the two dirty worktrees.
7. Integrate the runtime-cutover contract: strict installed-runtime
   provenance, content-addressed runtime binding/rebind/rollback, CAS marker
   update, supervisor receipt verification, and worker preflight enforcement.
8. Resolve overlaps semantically. Never choose a side of a conflict merely
   because it is newer; retain M9 projection/WBC behavior and the stricter
   custody invariant.
9. Run focused tests after every unit and the release validation pyramid after
   the final merge.
10. Push the canonical integration branch and verify its full SHA through
    `git ls-remote` before constructing a runtime.

## Runtime-convergence work required before cutover

The live system currently has multiple contradictory authorities:

- marker/relaunch identity: old `92aee998` capsule;
- actual editable package in that capsule: `aeeffea8ba`;
- chain execution binding: an older `6788980` lineage;
- resident source: `8ec28d6853`;
- supervisor source/receipt: separate older lineages.

The existing content rebind intentionally ignores runtime fields, the marker
updater has no compare-and-swap runtime transition, and the runtime provenance
check does not fully audit `.pth` state. Therefore the candidate may not be
activated until the integration branch supplies:

1. A separate, content-addressed runtime identity and A→B/B→A rebind ledger,
   without rewriting the immutable spec/asset binding history.
2. A CAS-protected marker update that rejects concurrent changes and replaces,
   rather than merge-retains, obsolete runtime fields.
3. Validation that Git HEAD, import roots, `direct_url.json`, every applicable
   `.pth`, interpreter, supervisor receipt, resident environment, marker, and
   chain runtime binding all name the same full SHA/root.
4. A worker preflight that reads the canonical chain spec/bound runtime rather
   than silently passing a chain-state JSON path and empty expectations.
5. Failure-injection tests for interruption after candidate install, marker
   update, supervisor restart, child spawn, and first state read.

## Release validation

### Focused contract tests

- V1 and V2 blocker IDs both validate against their immutable fingerprint;
  forged or identity-free requests remain unclaimable.
- Same-basename and same-batch retries choose the accepted current attempt,
  not lexical order, mtime, or highest batch number.
- `CASExpectation` cannot enter authority reduction.
- A quality-block recovery performs exactly:
  receipt resolution → recover-blocked → pinned relaunch.
- A dead review worker is not treated as an external PR/CI guard when the
  active repair phase says otherwise.
- The captured gate output missing the four strict fields is rejected, and the
  fixed prompt emits all required fields without validator synthesis.
- Stale gate/replan cursors, stale epochs, stale receipts, and stale runtime
  identities continue to block.

### Incident replay

Replay the captured M9 artifacts read-only. Require:

- completion authority is `(True, [])` using the existing signed receipt;
- the accepted-attempt projection is present;
- valid evidence permits exactly one M9 completion append and one M10 init;
- invalid evidence permits neither;
- repeated resume is idempotent.

### Runtime and restart

- Build a new immutable runtime root and new virtual environment from the
  advertised candidate SHA. Do not mutate the old `92aee998` environment.
- Test imports both with and without `PYTHONPATH`; parent CLI, subprocesses,
  wrappers, resident, supervisor, repair loop, watchdog, and auditor must all
  resolve the candidate.
- Run an action-off fake plan, the captured M9 read-only admission, and one
  bounded new-plan canary.
- Run focused suites, wrapper syntax checks, `ruff`, `git diff --check`, and a
  broad suite to completion. A timeout with unclassified failures is not a
  release pass.

## Atomic cutover

Preconditions:

- M10 remains drained: `active_step=null`, no Python/model/effect child.
- The old supervisor remains stopped.
- Integration branch is clean, fully pushed, and `ls-remote` returns its exact
  full SHA.
- All port-ledger rows are resolved and release validation is green.
- Candidate root and virtual environment are new, clean, and immutable.
- A single cutover lease/fence prevents watchdog, resident, and manual
  operators from switching concurrently.

Sequence:

1. Use durable operator pause; snapshot and hash chain state, marker, hot env,
   supervisor selector/receipt, old runtime, and process list.
2. Build the candidate root/venv from the exact pushed SHA; validate imports,
   `.pth`, metadata, Git, and dependency lock/digest.
3. Prepare the supervisor from the candidate and verify its receipt before
   selection.
4. Atomically update all runtime source selectors:
   `MEGAPLAN_RUNTIME_SRC`, `MEGAPLAN_SUPERVISOR_SOURCE`,
   `CLOUD_WATCHDOG_ARNOLD_SRC`, `MEGAPLAN_META_ARNOLD_SRC`, and
   `MEGAPLAN_AUDIT_ARNOLD_SRC`.
5. Append the content-addressed runtime rebind receipt and CAS-update the
   marker/relaunch attestation. Preserve earlier plan/phase provenance as
   history; record the new SHA only for the resumed gate invocation onward.
6. Restart only the intended supervisor/resident. Verify `/proc/.../environ`,
   actual imported files, Git SHA, supervisor receipt, marker, and chain
   runtime binding all agree.
7. Resume the existing M10 gate. Its first legal action is a fresh gate
   invocation from the durable repair cursor, not execution or an external
   effect.
8. Watch through `gated/finalized` into a live execute worker with fresh
   telemetry, then through at least one durable batch receipt. Only then call
   the chain “durably executing.”

Rollback:

- Keep the old source root and a separately constructed clean old runtime.
- On any mismatch, remain paused; atomically select the old clean runtime,
  append a B→A rollback receipt, restart the intended processes, and reverify.
- Never restore the contaminated old marker/venv blindly, rewrite plan
  evidence, downgrade schemas, append completion, or run an effect during
  rollback.

## Cleanup after acceptance

No source branch, worktree, bundle, or historical runtime is deleted as part of
this implementation. After M10 acceptance and a clean M11 start, prepare a
per-item deletion list with positive supersession evidence. Deletion requires
explicit user approval.

## Confidence and open gates

High confidence:

- The current gate block has a deterministic prompt/schema mismatch and a
  fail-closed fix with focused coverage.
- `3978c099ef` is exactly duplicated by `6633d792c5`.
- The overnight stack must be ported semantically rather than merged wholesale.
- Switching the current editable checkout in place would be unsafe.

Open until implementation completes:

- Destination SHAs and final focused-suite counts for the overnight, older,
  dirty-worktree, and runtime-cutover lines.
- Completion of the broad release suite.
- A fully consistent post-cutover runtime attestation and first durable M10
  execute receipt.

## Provenance

This plan is based on read-only surveys of the complete Hetzner `/workspace`
volume, the live M9/M10 plan/chain state, process environments, package metadata,
runtime marker, repair queue, the local Mac checkout, and disposable
cherry-pick/conflict tests. Investigation was split across the live-chain,
remote-custody, and runtime-receipt agents; exact source bundles and archive
refs were created before integration.
