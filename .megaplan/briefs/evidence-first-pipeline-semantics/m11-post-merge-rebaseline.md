# M11: Post Merge Rebaseline

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

After the epic lands, rebuild the frozen driver engine from the merged result and re-run the four motivating failure scenarios as regression proof: silent model degrade, engine/target contamination, phantom dependency, and frozen config.

This validates the epic against its own failure class rather than only proving each milestone in isolation.

## Scope

IN:

- Rebuild or refresh the frozen driver engine from the merged result.
- Run the silent premium->DeepSeek degrade regression and require a loud capability/routing denial or waiver.
- Run the contamination/dogfood-shadow regression and require isolation refusal or recorded local-dev waiver before mutation.
- Run the phantom-dependency regression and require authority readers to resolve divergence down before dependent work starts.
- Run the frozen-config regression and require resumed routing to recompute from pinned inputs and current capability, emitting `routing_resolution_decision`.
- Produce a post-merge regression report with commit SHA, driver engine pin, target head, command evidence, and links to relevant decisions/waivers.
- Document any remaining legacy/prose/human-deferred behavior as explicit residual risk, not as silent pass.

OUT:

- Do not add new feature scope after merge.
- Do not re-plan the epic from scratch.
- Do not accept reviewer prose as proof when command/evidence artifacts are available.
- Do not leave the rebuilt driver engine ambiguous or unpinned.

## Locked Decisions

- The post-merge driver engine is rebuilt from the merged result before validation.
- The four motivating failure scenarios are the required regression proof.
- Regression proof must cite evidence and decisions, not just narrative summaries.
- Any residual risk is explicit and operator-visible.

## Open Questions

- Whether this milestone runs as the final chain milestone or as a release-gate checklist outside the chain.
- Exact harness location for the four motivating regression scenarios.
- Which report format is canonical for post-merge evidence.

## Constraints

- Keep the rebaseline focused on the motivating failures, not a full new audit.
- Avoid mutating unrelated plan dirs or workspaces.
- Make results reproducible from the recorded merged commit and driver engine pin.
- Preserve manual merge policy; this milestone proves the merged result after the human merge.

## Done Criteria

1. The frozen driver engine is rebuilt or refreshed from the merged result and its pin is recorded.
2. The silent model degrade regression produces capability evidence and a loud gate result.
3. The contamination regression proves engine/target isolation or an explicit recorded local-dev waiver.
4. The phantom-dependency regression proves uncorroborated done resolves down and does not unblock dependent work.
5. The frozen-config regression proves routing recomputes from pinned inputs and emits `routing_resolution_decision`.
6. A post-merge regression report records commit SHA, driver engine pin, target head, command evidence, decisions/waivers, and residual risks.
7. Tests or scripted scenarios are repeatable and documented.

## Touchpoints

- driver engine rebuild/bootstrap
- regression scenario harnesses
- routing/capability tests
- isolation/dogfood-shadow tests
- authority-reader phantom-dependency tests
- config-reroute regression tests
- post-merge report artifact

## Rubric

- Profile: `directed`
- Robustness: `full`
- Depth: `low`

Rationale: this is validation and packaging rather than new architecture. The work is bounded, but it needs enough rigor to prove the epic closes the exact failures that motivated it.

