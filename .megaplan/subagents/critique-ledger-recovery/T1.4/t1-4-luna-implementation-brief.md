# GPT-5.6 Luna implementation brief — T1.4 deterministic graph repair

Do not start this implementation until the independently accepted Run Authority
contract has been placed on the clean recovery integration lineage. The current
main commit `36a10988717f9dfb0ab31d49baf05cc89bcfa989` lacks that package/API;
inventing a local substitute would create a forbidden shadow authority.

When that prerequisite is true, create a fresh isolated worktree from the exact
integration commit and implement T1.4 end to end:

- At the planning/finalizer graph-admission boundary, turn deterministic schema,
  semantic, topology, coverage, or policy rejection into a typed
  `planner_repair_required` object. Bind exact project/plan/iteration/object
  revision, graph candidate/raw capture/contract bundle, stable semantic error
  fingerprint, invalid pointers, producer/runtime identity, and domain policy
  version. Prose, error formatting, model, process, restart, or projection
  changes must not change the fingerprint.
- Store fingerprint and bounded repair budget in the canonical domain owner;
  store occurrence/lineage in Custody; store each effect attempt/ambiguity under
  WBC; require Run Authority to accept the one transition. These are joined
  records, not copied JSON authority. Read errors or unavailable owners fail
  closed.
- Allow exactly one narrow repair against the same object revision and contract
  bundle. It may change only independently proven invalid graph fields/pointers,
  must preserve every valid field, and must undergo full admission again.
  Budget exhaustion is terminal for that fingerprint/revision and cannot be
  reset by fresh sessions, model/provider swaps, rewording, restart, copied
  workspaces, projections, or a new process.
- While graph admission is rejected or repair authority is absent/ambiguous,
  execute, publish, notify, launch, Git/PR, cloud, and deployment effects must be
  inadmissible through the shared authority/WBC boundary.
- Remove or hard-fail every alternate graph/finalizer retry, generic worker JSON
  repair, override, watchdog, marker, and cloud wrapper path that can reset the
  budget or proceed without the accepted graph transition. Preserve ordinary
  unrelated provider-transient retry policy.
- Provide installed CLI/API and materialized-wrapper parity. Add adversarial
  tests for identical semantic failures with different prose/models/processes,
  restart/copy/concurrency, forged/missing domain/Custody/WBC/RA records,
  response loss, pointer widening, valid-field mutation, bundle/revision drift,
  budget exhaustion, two initializers, and zero downstream effects.

Primary mapped surfaces include:

- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/handlers/shared.py`
- `arnold_pipelines/megaplan/workers/_impl.py`
- graph/schema/plan validation under `arnold.pipeline` and Megaplan orchestration
- planning workflow/retry policy and all materialized cloud wrappers
- the accepted Run Authority, Custody, and WBC APIs on the integration lineage

Run focused, dependency-closure, concurrency/crash, installed-wheel, wrapper
parity, and bypass-inventory tests. Commit only scoped changes, leave a clean
worktree, and write exact commit/tree/test/evidence results under
`.megaplan/subagents/critique-ledger-recovery/T1.4/`. Local green tests are not
formal T1.4 completion without integration owner receipts.
