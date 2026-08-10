# Investigate North Star Actions Core Failure

Independently inspect the live Workflow Boundary Contracts gate-loop evidence and relevant Megaplan implementation. Answer the user's precise question: was `north_star_actions` absent from the milestone brief or North Star input, absent from the model's gate response, or present but dropped by an internal normalization/validation seam?

Trace the complete contract path: initiative brief and NORTHSTAR/anchor inputs; gate prompt and expected output schema; raw gate worker output if available; normalization/allowlist logic; structural validation; orchestration and same-phase retry behavior; automated repair classification/custody. Use the live run logs/state and repository history/diff as evidence, preserving unrelated uncommitted work.

Identify the deepest process failure rather than stopping at the missing-field exception. Distinguish input precondition failures from internal producer/consumer schema drift. Recommend the strongest systemic solution, including where launch-time validation is appropriate and where it would be misleading, schema derivation/single-source-of-truth, compatibility/default semantics, retry circuit breakers, typed failure classification, and regression tests. If safe and clearly within scope, implement and verify the corrective changes already underway; otherwise provide an evidence-backed diagnosis and exact corrective boundary. Do not restart the resident, alter cloud chains, push, commit, or open a PR.

Return a concise user-facing summary that clearly explains whether the brief was at fault, why the gate repeated dozens of times, and what prevents recurrence.
