# Resident operator task: Run Authority profile/duplicate correction

Investigate the two live Run Authority chains reported by the canonical cloud status snapshot generated at 2026-07-11T13:40:04.733603Z:

- `runauthority-epic-all-codex`, newly started, 4% overall / Sprint 1 12%, critique evaluator active.
- `runauthority-epic-cloud`, the established run, 100% progress with Sprint 3 in review.

The user states the intended profile is `partnered-5`, not all-Codex, and is surprised a second run exists.

Act as a durable Megaplan operator. Determine from canonical manifests, chain specs, run provenance, and supported introspection surfaces whether the newly started all-Codex chain is erroneous, duplicative, or merely misleadingly named. Preserve the established partnered-5 run. If the new chain is clearly unintended and a safe supported control action exists, stop/cancel only that incorrect run and verify the partnered-5 run remains healthy. Do not use arbitrary remote shell commands, kill processes directly, disturb unrelated chains, rewrite Git history, or launch another chain. If cancellation/profile correction requires human approval or remains materially ambiguous, do not mutate it; report the exact gate and safest next action. Also identify how the unintended launch occurred if evidence permits.

Return a concise result including both run identities, actual configured profiles, actions taken, verification evidence, and any remaining human decision.
