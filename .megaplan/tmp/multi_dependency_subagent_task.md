Implement durable multi-predecessor dependency support for resident-managed subagents, so a queued successor can accept multiple predecessor run IDs and launch only after all predecessors have completed successfully.

Scope and ownership:
- You are the sole implementation, synthesis, and Discord delivery owner for this request.
- Inspect the pinned resident runtime checkout as well as the current project checkout. Preserve concurrent dirty work.
- Use an isolated worktree and feature branch based on the verified canonical resident-source target revision. Do not infer literal main.
- Own the resident launch API/CLI, queue manifests/state transitions, validation, status/inspection presentation, compatibility, tests, documentation/help text where needed, and local integration.
- Do not restart the resident, push remotely, deploy, or alter currently running agents.

Required behavior:
- Extend the current depends_on_run_id success-gated successor facility to support multiple predecessor IDs through a clear backward-compatible contract (for example depends_on_run_ids while retaining the singular field).
- A successor must remain queued until every distinct predecessor succeeds with a valid result.
- Any predecessor failure, cancellation, invalid result, or supersession must fail/propagate closed according to existing semantics; bounded retry and cycle safety must continue to hold.
- Validate malformed values, duplicates, self-dependencies, missing runs, and dependency cycles deterministically.
- Make queue inspection and manifests expose the complete predecessor set and enough per-predecessor state to explain why a successor is waiting or failed.
- Preserve immutable Discord/delegation provenance and the exactly-one delivery-owner rules.
- Define deterministic behavior for legacy singular callers and any mixed singular/plural inputs.
- Do not retrofit or mutate already-running runs from the earlier strategic analysis; this is platform support for future launches.

Verification and delivery:
- Add focused regression tests covering two-or-more predecessor fan-in, partial completion (must not launch), all-success launch exactly once, failure/cancellation/invalid-result propagation, duplicate/mixed inputs, cycle rejection, backward compatibility, restart/reconciliation idempotence, and provenance/delivery ownership.
- Run proportional relevant test suites and review the final diff.
- Commit the verified change and locally integrate it into the unambiguous verified resident-source target using the repository's non-destructive method.
- Before claiming completion, record base revision, target revision, commit SHA, tests/checks, reviewed diff, clean isolated worktree, and ancestry evidence that the target contains the commit.
- If the target is materially ambiguous, history is rewritten/conflicting, or integration authorization differs, leave the verified commit isolated and report the exact approval gate instead of guessing.
- Deliver one concise user-facing completion to the originating Discord request, distinguishing implementation/integration from deployment or activation.
