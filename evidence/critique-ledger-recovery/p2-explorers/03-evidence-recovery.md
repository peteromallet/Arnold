# Luna explorer 3 — evidence ordering and recovery state machine

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Return under 1200 words with exact
evidence.

Read `sol-p2-framing-result-20260804.md`, `sol-final-plan-20260804.md`, and
`luna-vj9-review-20260804.md`. Known symptoms: VJ9 was recorded in history and
artifact but `latest_failure` was null; stale `phase_result.exit_kind` could
outvote a newer failure; status projections disagreed; generic recovery paths
were suggested for deterministic validation failures.

Audit `arnold_pipelines/megaplan/run_state/`, `orchestration/phase_result.py`,
`blocker_recovery.py`, `handlers/override.py`, decision-contract/resume logic,
state/history writers, and status projections. Reconstruct the current
precedence and identify every way an old artifact can clear, downgrade, or
misclassify a newer occurrence.

Recommend the minimal occurrence/fingerprint/generation schema, compare-and-swap
transition rules, and recovery API. Give concrete tests for wrong occurrence,
stale phase result, replayed receipt, terminal telemetry, and VJ9/VJ8-style
validation blocks. Separate automatic repair from human gates.
