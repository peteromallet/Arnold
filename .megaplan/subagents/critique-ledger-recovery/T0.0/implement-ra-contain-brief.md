# T0.0 Luna implementation brief — installable RA-CONTAIN owner surface

You are the GPT-5.6 Luna implementation owner for the missing capability proven
in `/Users/peteromalley/Documents/Arnold/evidence/critique-ledger-recovery/T0.0/`.

Work only in the clean isolated worktree:

`/private/tmp/arnold-critique-recovery-ra-contain-20260802`

It is based on clean release-candidate commit
`6787d6363e8fc0603092913ae877db14f3b9fff8`. Preserve every other checkout.

Goal: implement the smallest production-quality, fail-closed Run Authority
owner interface that can make task T0.0 executable. It must durably issue,
query/audit, terminate/revoke, and independently verify an append-only
`RA-CONTAIN` incident decision bound to an exact poisoned tuple. It must deny
new `resume`, `repair`, `execute`, `publish`, `notify`, and deployment effects
while preserving read-only observation. It must return an owner receipt with a
decision ID, exact scope, expected prior owner cursor/revision (CAS), TTL or
explicit termination policy, issuer, created time, content hash, and audit/revoke
path. Stale CAS, missing/corrupt state, conflicting duplicate identity, unknown
effect, expired authority, or torn/incoherent storage must fail closed.

Read before editing:

- `arnold_pipelines/run_authority/contracts.py`
- `arnold_pipelines/run_authority/reducer.py`
- `arnold_pipelines/run_authority/current_source.py`
- all Run Authority tests and current CLI registration patterns
- `/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`
- T0.0/T0.1 and the evidence/interface registry in the recovery plan

Architecture constraints:

- Run Authority owns this journal/interface. Do not route the write through
  Custody, WBC, watchdog, tmux, marker, resident, or a shell convention.
- Owner-local atomicity only. Use append-only, fsync/atomic durability and a
  process-safe singleton/CAS discipline appropriate to the existing repository.
  Never claim cross-system atomicity.
- The durable journal is authority; projections/query views are rebuildable.
- A digest is integrity evidence, not a fabricated cryptographic signer. If the
  repo has an accepted signing primitive, reuse it; otherwise name the receipt
  `content-addressed` and do not call it signed.
- This task installs an interface; it does not deploy or mutate the live cloud.
- Do not enable legacy repair topology or create a generic retry owner.
- Use `apply_patch` for source/test edits. Do not overwrite unrelated work.

Required interface behavior:

1. `issue containment` with exact tuple, denied effect classes, preserved read
   class, expected cursor/revision, TTL/termination, issuer/reason.
2. `status/audit` that rebuilds from authority and exposes current cursor plus
   receipt/digest without granting mutation.
3. `terminate/revoke` under expected cursor/revision, append-only (never edit a
   prior record).
4. a pure verifier/policy check that downstream T0.1 effect boundaries can call
   and that rejects missing/incoherent/unknown input.
5. an operator CLI/API consistent with this repo, JSON output, useful typed exit
   results, and no implicit defaults for incident scope.

Minimum tests:

- issue/query happy path and exact tuple binding;
- every denied effect rejected while reads remain allowed;
- stale CAS and concurrent issuers allow one accepted append;
- identical replay is idempotent; divergent duplicate is typed and quarantined
  or `INDETERMINATE`, never a second accepted decision;
- terminate/revoke is append-only and makes subsequent checks reflect it;
- TTL/expiry behavior uses injected time and fails closed;
- truncated/corrupt/torn journal, missing path, unknown effect, and wrong tuple
  fail closed;
- restart/replay deterministically rebuilds the same state/digest;
- CLI JSON contract and nonzero refusal exits.

Run focused tests, then the broadest affordable Run Authority/CLI regression
suite. Run `git diff --check`. Commit the complete change on the existing task
branch with an intentional message. Do not push.

Write a concise implementation handoff to
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T0.0/ra-contain-implementation-result.md`
using `apply_patch`. Include commit SHA, changed files, exact CLI/API, tests and
exit codes, remaining deployment/acceptance requirements, and any honest gaps.

Completion means code + tests + commit + handoff, not a design memo. Keep going
until that is true or a precise, non-workaround blocker is proven.
