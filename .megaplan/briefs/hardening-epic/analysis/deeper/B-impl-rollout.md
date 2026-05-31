# B — Completion Contract: Rollout, Performance, Edge Cases

Operational realities of shipping the fail-closed `CompletionContract`
(`B-completion-contract-{claude,codex}.md`). The contract is settled; this is *how to
land it without bricking currently-green flows*.

## 1. Rollout — shadow → warn → enforce

A global fail-closed flip would block flows that pass today (the suite itself has
~4 currently-RED tests, §2). Gate enforcement behind a mode, defaulting to the *safest*
phase first.

**Mode flag.** Add `completion_contract_mode: NotRequired[str]` to `PlanConfig`
(`types.py:95-110`) with values `off | shadow | warn | enforce` (default `shadow`).
Mirror it as a chain field `completion_contract_mode: str = "shadow"` on `ChainState`
(`chain/__init__.py:434`) so a chain pins one mode across milestones. Resolve via the
existing `execution.*` settings table (`types.py:673-713`): add
`"execution.completion_contract_mode": "shadow"`.

**Behavior per mode** (all modes *compute* the `CompletionReport` and write
`completion_verdict.json`, so we accrue data from day one):
- `off` — compute nothing; legacy path.
- `shadow` — compute + persist verdict; **never** alter `status`. Emit a
  `COMPLETION_VERIFICATION_SHADOW` trace event with `passed`/failures.
- `warn` — as shadow, plus surface failures in `megaplan status` / chain status and
  `latest_failure` (non-blocking note), but still return `done`.
- `enforce` — the design's fail-closed behavior: deny terminal, return
  `verification_failed`/`blocked` (`auto.py:1363`, `chain/__init__.py:1418`).

**Graduation criteria (per evidence class, not all-or-nothing).** Graduate one evidence
class at a time from shadow→enforce when, over the dogfood corpus (this repo's own
hardening-epic runs): (a) shadow `unsatisfied` rate on *known-good* completed milestones
is < 2% and every such case is a real bug or a missing waiver (not a false positive);
(b) the waiver path (§3) has been exercised at least once per `reason_code`. Order:
`worker_did_work` (cheapest, lowest false-positive) → `landed_diff` → `phase_coverage`
→ `green_suite` last (most expensive + most env-sensitive). Per-evidence enforcement
lets `green_suite` stay in `warn` while diff/coverage already enforce.

## 2. Performance — the green-suite cost + caching

**Measured suite cost (this repo):** `3197` tests collected; full non-slow suite
`pytest -m "not slow and not integration"` = **390s wall (~6.5 min)**, even with low
CPU utilization (user 94s — heavily I/O / subprocess-bound, so not trivially
parallelized away). `_capture_test_baseline` already caps at a **120s timeout**
(`finalize.py:529`) — i.e. the *full* suite would already time out under the existing
runner. Running it at every plan-done **and** every milestone-done in a chain of N
milestones = N×6.5min of pure verification, dwarfing the work.

**Caching/dedup design** — `green_suite` must reuse a recent run, never re-run blindly:
1. **Reuse the baseline run.** `finalize.json` already stores
   `baseline_test_failures` + `baseline_test_command` (`finalize.py:555`). Stamp it with
   `baseline_captured_at` (ISO) + `baseline_head_sha` (`git rev-parse HEAD`).
2. **Freshness predicate.** `green_suite` reuses the baseline result iff
   `baseline_head_sha == HEAD` **and** no tracked file mtime is newer than
   `baseline_captured_at`. If fresh → the contract diffs *current* failures against
   baseline using the **already-captured** numbers; cost ≈ 0.
3. **Execute owns the authoritative run.** Make execute's own final verification run
   write a `verification/suite_run.json` `{head_sha, command, exit, failures, ran_at}`.
   `green_suite` at milestone-done reuses it when `head_sha == HEAD`. The suite runs
   **once per HEAD**, not once per terminal transition.
4. **Scope the run.** Honor `test_command` config (`finalize.py:502`) so a plan can pin
   a *narrow* command (the changed package) for per-milestone gates and reserve the full
   suite for plan-done. Raise the 120s timeout to a configurable
   `test_command_timeout` (default 900s) so the full suite can actually complete when
   intentionally run.
5. **`not_applicable` short-circuit.** Docs-only / prose plans (§3) skip the run
   entirely via waiver — no suite cost.

## 3. Edge-case handling

| Case | Contract behavior |
|---|---|
| **Docs-only / prose plan** (`is_prose_mode`, `execute.py:204`) | `landed_diff` still requires a non-empty diff (the docs). `green_suite` finds a typed `docs_only` waiver in finalize.json → `not_applicable`. No suite run. |
| **Bare robustness** (`execute.py:211-222`, writes `STATE_DONE` directly) | Bare selects a *lighter* contract, never *no* contract: `worker_did_work` + `landed_diff` (or declared no-op) only; `green_suite`/review-disposition skipped. Cannot self-promote to `done` with zero diff and no waiver. |
| **No-PR path** (hardening epic: branchless milestone) | Decouple verification from `use_pr = push_enabled and bool(milestone.branch)` (`chain/__init__.py:1211`). Verify against the **working tree** baseline (§4), not a PR head. This is also the dead-`merge_policy` fix: advancement gates on `report.passed`, not branch presence. |
| **Cloud runs** (`megaplan cloud`) | Contract runs *inside* the container where the repo + deps already live; the entrypoint must ensure `test_command` deps are installed. `suite_run.json` lives on the persistent workspace volume so reuse survives operator-loop restarts. Honor `test_command_timeout` generously (containers are slower / cold). |
| **Chained milestones, accumulating diff** | See §4 — scope landed-diff to *this* milestone's commits via a per-milestone baseline SHA. |

## 4. Diff-scoping — per-milestone baseline checkpoint

The known worktree-carry problem (m5a): in a chain the working tree carries prior
milestones' commits, so a naive `git diff base_branch..HEAD` attributes *all* prior
work to the current milestone. Fix: **checkpoint HEAD at milestone start**.

- `_branch_head(root)` (`chain/git_ops.py:461`, plain `git rev-parse HEAD`) already gives
  the anchor. At milestone start (right after `_checkout_milestone_branch`,
  `git_ops.py:202`), record `milestone_base_sha = _branch_head(root)` onto `ChainState`
  (new field, persisted in `to_dict`, `chain/__init__.py:451`).
- `CompletionContext.git_base_ref` (already in the design,
  `B-completion-contract-claude.md:51`) is set to `milestone_base_sha`, **not**
  `base_branch`. `landed_diff` then runs `git diff --stat <milestone_base_sha>..HEAD`,
  isolating exactly this milestone's commits even when prior milestone commits are
  present in the tree.
- For the single-plan driver (`auto.py`), the baseline is HEAD at plan start (no chain),
  captured the same way and stored in state.
- Edge: a milestone that makes **zero** commits (carried WIP only) now correctly shows an
  empty milestone-scoped diff → `landed_diff` `unsatisfied` unless a waiver exists,
  catching exactly the m5a false-pass.

## 5. Failure-recovery UX

On `enforce` failure the plan goes **blocked** (never `done`), reusing
`_record_lifecycle_failure` (`auto.py:741`):
- `latest_failure.kind = "completion_verification_failed"`, `suggested_action =
  "Inspect completion_verdict.json; satisfy or waive failed evidence."`,
  `recoverable_via` set to the override step.
- **Inspect:** `megaplan status` renders `completion_verdict.json` (every `EvidenceRef`
  + observed facts: diff paths, new-failure list, tool-call count).
- **Waive:** the existing override handler (`handlers/override.py`). A new
  `override-waive-evidence` action appends an `EvidenceRef(status="waived",
  kind="human_waiver", details={reason_code, note, author})` to the verdict —
  mirroring `_override_force_proceed` (`override.py:209`). It **does not mutate the
  failed evidence to pass**; the objective failure stays on record (matches harness
  philosophy: failures are accepted, never erased).
- **Resume:** override clears the block and re-drives the terminal transition; on the
  next pass the contract sees the waiver and returns `not_applicable` for that evidence,
  so completion proceeds. `recoverable_via` already routes `megaplan auto` resume here.

---

### 5-line summary
1. **Suite runtime: ~390s (6.5 min) for 3197 non-slow tests** — running it at every
   terminal transition would add N×6.5min to a chain; the existing baseline runner even
   caps at 120s (would already time out).
2. **Recommended rollout:** add `completion_contract_mode` (off/shadow/warn/enforce,
   default `shadow`) to `PlanConfig`/`ChainState`; graduate **per evidence class**
   (`worker_did_work`→`landed_diff`→`phase_coverage`→`green_suite` last) when shadow
   false-positive rate <2% on known-good runs.
3. **Green-suite caching:** run the suite **once per HEAD**, stamp `baseline_head_sha`/
   `_captured_at` on finalize.json, reuse it when HEAD + mtimes unchanged; raise the
   120s cap to a configurable `test_command_timeout` (default 900s).
4. **Diff-scoping:** checkpoint `milestone_base_sha = _branch_head(root)` at milestone
   start and diff `<milestone_base_sha>..HEAD`, fixing the m5a worktree-carry false-pass.
5. **Recovery:** failure → `blocked` + `completion_verdict.json`; a new
   `override-waive-evidence` adds a `waived` ref (never mutates the failure), and
   `recoverable_via` resume re-drives the now-passing transition.
