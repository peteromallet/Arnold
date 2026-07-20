# Narrow superfixer compatibility repair

Work only in `/workspace/superfixer-custody-fix-20260714`, a clean worktree based on `origin/editible-install` commit `9686c0fc3ffe1f398605a06a05bdc014fbc3bab8`.

Diagnosed defects:

1. `handlers/review.py::_deterministic_review_block_evidence` recognizes only exact status strings `fail`, `failed`, or `error`. The live review artifact uses strings such as `failed: green_suite remains unsatisfied`, so five executable deterministic checks were dropped and the plan was persisted as `review_quality_blocked_unknown` with empty evidence.
2. `cloud/repair_contract.py::_is_known_repairable_shape` lost `quality_gate_blocked` and `deterministic_quality_blocked` during commit `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`, although `project_repair_custody` still grants exactly one attempt and `tests/cloud/test_recovery_decision_systemic.py::test_exhausted_deterministic_quality_dispatches_one_bounded_repair_without_human` expects L1 dispatch.
3. The original accepted/unclaimed request already contains the legacy misclassified token `review_quality_blocked_unknown`. A future-only writer fix will not recover this session. Add the narrowest fail-closed compatibility path in the ordinary repair trigger/classifier: it may reinterpret that exact legacy token as deterministic quality only when the authoritative current plan `state.json` path has a sibling `review.json` whose blocking `rework_items` contain nonempty executable checks and failure-like detailed statuses under the same fixed parser. Do this in memory for dispatch; do not rewrite plan state, fabricate success, auto-approve, weaken review gates, execute checks, or make arbitrary unknown blocks repairable. Preserve the one-attempt budget and evidence cursor/fingerprint custody. If there is a cleaner existing abstraction, use it.

Implement tests proving:

- statuses such as `failed: detail` produce `quality_gate_blocked` and structured deterministic evidence;
- both quality tokens are L1-repairable only with current-target evidence;
- a legacy `review_quality_blocked_unknown` request is upgraded only when its authoritative sibling review artifact contains qualifying executable deterministic failures;
- missing/malformed/non-failing review evidence remains `broken_superfixer`, never L1 or human approval;
- retry budget remains one, and typed human gates remain human-only.

Run the focused systemic recovery tests, relevant repair-trigger tests, and wrapper syntax/tests. Inspect the entire diff for unrelated changes. Commit the narrow change on the current branch with a descriptive message. Do not push, deploy, modify the live session, run review/execute commands, restart watchdog/chain, or touch `/workspace/arnold` or `/workspace/.megaplan/repository-strategy-roadmap-supervisor-source`.
