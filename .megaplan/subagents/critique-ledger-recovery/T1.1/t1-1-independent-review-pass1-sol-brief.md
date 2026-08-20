# T1.1 raw-evidence admission — independent GPT-5.6 Sol-high review pass 1

This is a read-only, adversarial review of the candidate in
`/private/tmp/arnold-critique-recovery-t1-1-admission-20260802`.

Exact candidate:

- base/parent: `6787d6363e8fc0603092913ae877db14f3b9fff8`
- commit: `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`
- tree: `f6c83fca884e9631c7518810ee521d75389815b3`
- implementation report:
  `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-sol-implementation-result.md`

Do not modify source, worktree, git, checklist, cloud/provider state, owners,
markers, plans, or processes. You may run finite read-only tests. Large suites
must be single-flight. Write only the review report named below.

## Review standard

Try to falsify the claim that every production materialization and mutation
path is admitted from the exact raw eight-role authority set, through an
owner-authenticated decision and deterministic CAS/reconciliation boundary,
with no projection/caller assertion capable of minting authority.

Scrutinize these known limitations rather than accepting them as benign:

1. The public/internal `allow_non_production_backend=True` switch. Determine
   whether ordinary shipped code can select the hermetic backend or otherwise
   caller-mint an accepted decision. Require a capability-sealed or separately
   packaged test boundary if the current seam is forgeable.
2. Root milestones with no `depends_on` and no
   `prerequisite_policy: required`. Determine whether any ordinary root launch
   can bypass CL1/Run Authority. A platform-wide policy needs an explicit,
   owner-allowlisted no-prerequisite contract; absence must not silently mean
   bypass.
3. Revisionless `ChainState`. Probe competing writers, stale projections,
   crash/replay, missing marker, replacement plan directories, state rollback,
   and response loss. Projection state must not overrule owner truth.
4. Missing owner backend/lookup behavior. Production absence, stale owner
   revision/fence, missing marker, and intended-plan reconciliation must fail
   closed without rematerialization or a second launch.
5. Every source, installed-wheel, direct-module, wrapper, supervisor, legacy,
   handler, custom runner/driver, auto/resume/finalize/override and non-Megaplan
   materialization path. Static inventory alone is insufficient if dynamic or
   import aliases escape it.
6. The eight raw roles: reviewer verdict, coherence evidence, proof result,
   ownership map, portfolio decision, amendment record, blocker register, and
   checked handoff projection. Missing/duplicate/extra/substituted/symlinked/
   truncated/corrupt/replayed roles and projection disagreement must not grant.
7. Deterministic request, intended-plan identity, reservation, materialization
   claim/completion, exact replay, conflict, process concurrency, crash cuts,
   late fence/expiry, and lost response. No duplicate side effect or alternate
   plan identity may appear.
8. Installed/source parity and the negative T0.2 fixture. Preservation evidence
   must not become live admission authority.

Use concrete code references and reproduce blockers with minimal hostile tests
where practical. Distinguish:

- **BLOCKER**: a reproducible false success, duplicate effect, lost/corrupt
  authoritative evidence, unsafe retry, broken fencing, or ordinary bypass.
- **NONBLOCKING LIMITATION**: broader hardening or redesign with no ordinary
  exploit/reproduced critical-path failure.

Do not demand arbitrary interpreter takeover defenses or mathematical
impossibility. Do not let speculative redesign block a narrowly fenced canary.

## Output

Write a self-contained PASS or HARD FAIL report to:

`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.1/t1-1-independent-review-pass1-sol-result.md`

Include exact reviewed commit/tree/parent, commands and counts, each reproduced
blocker, nonblocking limitations, and a SHA-256 of the report. Do not claim
formal T1.1 completion: deployed owner/integration receipts remain separate.
