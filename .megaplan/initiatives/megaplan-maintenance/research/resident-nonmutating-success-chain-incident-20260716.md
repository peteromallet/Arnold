# Resident non-mutating success-chain incident — 2026-07-16

## Scope and authority

This is the canonical diagnosis and verification record for Discord source
`msg_dfab6b2b7c55`, covering the failed four-stage chain rooted at
`subagent-20260716-182026-660e0d43`. It records evidence; it does not authorize
a resident restart, deployment, push, or historical-state rewrite.

The resident-source target was resolved from launch custody, not inferred:
`refs/heads/consolidate/arnold-runtime-activation-20260714` at
`235472012dc3dcada37207b39e65f7fcc8675185` in
`/workspace/arnold-consolidation-20260714`. The project checkout
`/workspace/arnold` was on `refs/heads/main` at
`72f7eec32b3fdf8f5027a415d97f0e14716773f4`; both launch checkouts were dirty
and were preserved. Implementation used the separate worktree
`/workspace/arnold-resident-nonmutating-verification-fix-20260716` and branch
`refs/heads/fix/resident-nonmutating-verification-contract-20260716` from the
recorded resident base.

## Historical chain: observed evidence

All raw artifacts are under `.megaplan/plans/resident-subagents/<run-id>/`.

1. `subagent-20260716-182026-660e0d43` executed from
   `2026-07-16T18:20:27.024085Z` through `2026-07-16T18:20:33.338078Z`.
   `result.md` contains exactly `WORD_1: lantern`; `run.log` shows the worker
   produced that final answer and contains no repository mutation claim. The
   terminal manifest instead records `status=failed`, `returncode=2`,
   `error="git custody verification failed"`, and a missing
   `git-custody-evidence.json`. Its delivery was correctly suppressed because
   it was an internal contributor.
2. `subagent-20260716-182042-237d3629` was committed queued at
   `2026-07-16T18:20:42.796826Z`, never started (`attempt_count=0`, no
   `started_at`, empty `result.md`, no `run.log`), and failed closed at
   `2026-07-16T18:20:51.438835Z` with
   `attention=predecessor_terminal_failure`. Its provisional delivery ownership
   was superseded by the third run; it did not send Discord output.
3. `subagent-20260716-182052-17a97ab9` was committed queued at
   `2026-07-16T18:20:52.235395Z`, never started (`attempt_count=0`, no
   `started_at`, empty `result.md`, no `run.log`), and failed at
   `2026-07-16T18:21:41.663960Z` with
   `attention=invalid_dependency_contract`. Its exact validation error was
   `queued successor must be the sole synthesis delivery owner`. Its delivery
   ownership was superseded by the fourth run; it did not send Discord output.
4. `subagent-20260716-182057-4d766029` was committed queued at
   `2026-07-16T18:20:57.733934Z`, never started (`attempt_count=0`, no
   `started_at`, empty `result.md`, no `run.log`), and failed closed at
   `2026-07-16T18:21:41.663960Z` with
   `attention=predecessor_terminal_failure`. It remained the sole synthesis and
   delivery owner. Its independent completion turn classified verification as
   `unknown`, and the outbox delivered the failure summary at
   `2026-07-16T18:22:06.467713Z` with provider outcome `accepted` and Discord
   message id `1527379811696119888`.

## Root cause and inference boundaries

Observed governing code at the pinned revision:

- `resident/subagent.py::_run_codex_manifest` applied git-custody validation to
  every zero-exit run whose `work_intent` was `execution`. It did not consult
  `task_kind` or a mutation claim. On missing evidence it set `returncode=2`,
  rewrote the terminal classification to failed, and reconciled successors.
- `resident/subagent.py::_validate_queue_authorization` required every queued
  successor to be `synthesis_delivery_owner`, even for same-request intermediate
  contributors. Queue construction also promoted queued runs to that role.
- `_queue_result_is_valid` then trusted only terminal `completed`, zero return
  code, and a non-empty result. The rewritten first manifest therefore caused
  correct fail-closed dependency propagation despite a substantively valid
  result.
- Completion-verifier input had no explicit applicable non-mutating success
  classification, which allowed delivery wording to fall back to `unknown`.

Inference: the first Codex worker exited zero before custody validation. This is
required by the observed branch condition that invoked custody validation, and
the log shows normal final-result production, but the pre-rewrite worker return
code was not separately persisted. Missing telemetry: runs 2–4 have no worker
logs because they never executed; the first manifest does not retain both the
raw worker return code and post-verification return code; user-notification
visibility for the delivered Discord message is recorded as `unknown`.

## General contract correction

The launch boundary now resolves and persists `mutation_claim` from
`task_kind`, `work_intent`, and any explicit claim:

- lookup/extraction/mechanical execution defaults to `none` and receives a
  non-mutating instruction with no git custody contract;
- an explicit `git_backed` claim, and every mutation-shaped execution task,
  retains strict isolated-worktree receipt validation;
- mutation-shaped execution cannot opt out with `mutation_claim=none`;
- an unexpected git-custody evidence artifact under a non-mutating contract
  fails closed as a contract mismatch.

Successful bounded non-mutating work now records
`completion_verification.classification=applicable_non_mutating_success` with
`git_custody=not_applicable`. Git-backed work records success only after
`git_backed_mutation_custody_verified`. Queue validation consumes these explicit
classifications, inherits the mutation claim, permits same-request internal
contributors, and retains sole-owner enforcement for cross-request delivery.
The independent completion-verifier prompt receives the same classification so
delivery text cannot invent git requirements for a non-mutating result.

## Verification and integration

Focused verification:

- `python -m pytest -q tests/resident/test_git_custody.py tests/resident/test_subagent_queue.py tests/resident/test_delegation_delivery_instruction.py tests/resident/test_task_routing.py`
  — 68 passed after the final safety regression.
- The same focused set plus the two compatibility cases surfaced by the wider
  run — 70 passed.
- `python -m pytest -q tests/resident/test_megaplan_initiatives.py` — 21 passed.
- A full `tests/resident` run reached 432 passed and two failures. One was a
  legacy-manifest compatibility gap introduced by the first draft and was fixed
  with explicit `legacy_lifecycle_success`; the other was a suite-order
  `tmux has-session` capture in a follow-up test. Both exact failures passed in
  the subsequent 70-test isolated run. The full suite was not rerun after that
  eight-minute pass; this distinction is intentional.
- Regressions prove: zero-exit non-mutating mechanical success without git
  custody; predecessor success launches its successor; a four-deep chain reaches
  exactly one final delivery owner; explicit git-backed mechanical mutation
  fails without custody; and predecessor failure propagates through every
  successor without execution.

The target advanced concurrently from the launch base to
`97cc9171f35f66b0d83bd40a0f0029106e321189` through four unrelated commits. A
first shell revalidation command lacked `set -e` and briefly moved the target ref
to the pre-rebase feature commit after a failed assertion. No checkout files
changed. The ref was immediately restored by compare-and-swap to `97cc9171f...`,
the feature was rebased, 70 focused tests were rerun, and guarded integration
then advanced the target to `31d72c3a85e20c0a76a1d5d96df2d7ce84d77ecb`.
Ancestry proves the launch base, the concurrent target revision, and the fix are
all retained.

## Fresh durable non-mocked chain

The integrated source was exercised through four real Codex workers in the
isolated durable proof project
`.megaplan/proofs/nonmutating-chain-31d72c3a85/.megaplan/plans/resident-subagents/`:

1. `subagent-20260716-185232-0ada2fe4` completed zero-exit with
   `WORD_1: lantern`.
2. `subagent-20260716-185232-bd11d7f0` launched only after validated predecessor
   success and completed with `lantern, meadow`.
3. `subagent-20260716-185232-22726cfd` launched only after validated predecessor
   success and completed with `lantern, meadow, pebble`.
4. `subagent-20260716-185232-e15c7338` launched only after validated predecessor
   success and completed with
   `WORDS_IN_ORDER: lantern, meadow, pebble, river`.

Every manifest records `status=completed`, `returncode=0`, and
`completion_verification.classification=applicable_non_mutating_success` with
`git_custody=not_applicable`. The first three are internal contributors with
`completion_delivery.status=suppressed`; only the fourth is the synthesis owner,
with delivery pending.

This is durable behavioral proof of the integrated source, but not a production
Discord delivery claim. The live Discord resident PID `2307050` was started with
`python -P` and resolves the installed editable module to
`/workspace/arnold-consolidation-20260714`, whose loaded source predates the fix
and lacks `COMPLETION_VERIFICATION_SCHEMA`. It also does not scan the isolated
proof project. Exercising the integrated target through the installed resident
therefore requires `agentbox services restart agentbox-discord-resident` (and
installed-source reconciliation). Restart/deployment was explicitly outside
this request, so it was not performed; final-owner user-facing delivery remains
the exact operational gate.
