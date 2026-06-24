# Reigh Foundation Closure - Prep

## Outcome

Close the original extension-foundation intent before broad Phase 4 family work starts. This is a narrow corrective epic, not a new extensibility sprint. It must turn the remaining partially fulfilled foundation contracts into code, tests, and release-gate evidence.

## Why This Exists

The prior pristine foundation chain substantially improved M5 readiness, but a forensic audit found the original foundation goal is still only partially fulfilled. The remaining gaps were mostly not missing from the briefs; they were lost through handoff and verification drift. This closure chain exists to finish those exact contracts and make the evidence durable.

Known remaining blockers:

- Proposal import is implemented on the concrete runtime but not exposed on the public `ProposalRuntime` SDK interface.
- The agent proposal vertical lacks one true edge response -> runtime import -> panel -> accept/apply test.
- Runtime `settings.set()` is not provider write-through on set; manager saves are healthier than runtime persistence.
- Readiness is not a normal release-quality gate and still allows anchor/document evidence to stand in for passing behavior.

## Execution Posture

Run this chain only with the Megaplan publication guard that blocks PR-backed milestone completion unless the published PR/merge diff contains semantic product work or a valid typed no-op waiver. The guard was added in the editable Megaplan install after the Reigh M3 split-brain incident.

Every milestone must update `docs/extensions/foundation-contract-ledger.md` with blocking contract status and executable evidence. The final milestone cannot mark the foundation cleared unless all blocking ledger rows are satisfied or explicitly waived.

## Anti-Scope

- Do not begin broad Phase 4 contribution families.
- Do not add marketplace, signing, sandboxing, remote install, or published external SDK packaging.
- Do not rework unrelated editor architecture.
- Do not treat documentation rows or anchor existence as behavioral proof.

