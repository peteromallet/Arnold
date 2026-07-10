# Sense-check adjustments — 2026-05-27

Input: ten independent DeepSeek V4 Pro reviews of `chain.yaml` and the milestone docs, each from a different lens (scope, abstractions, sequencing, safety nets, config, docs clarity, user value, maintainability, operability, adversarial). The reviews are preserved under `out/subagent_reviews/excellence_epic_chain/results/`.

This note records the human/primary-agent synthesis. The subagent findings were useful but not adopted wholesale.

## Accepted

- Split the old sprint 6 capstone. Runtime/session/RunPod work is now sprint 6; plugin collision policy, route/verb wiring, and release hardening are sprint 7.
- Make sprint 1 failing-first. The differential harness must first reproduce the known corrupted templates before the emitter fix and re-emission.
- Move stale node-spec deletion out of sprint 1 and into sprint 2, where the new consistency gates can prove the post-delete registry surface is intact.
- Add explicit handoff artifacts for every sprint (`handoff-mN.md`) so failures and review pauses are resumable without forensic rediscovery.
- Add prep deliverables for the high-risk sprints (`prep-m1.md`, `prep-m3.md`) instead of leaving `with_prep` implicit.
- Tighten M3 around an explicit IR contract, migration/version rule, and post-M3 revalidation of sprint-2 gates.
- Add a node-classification seam in M4 so code does not couple directly to schema-provider internals.
- Resolve the M5 contradiction: decomposition remains zero behavior change; user-facing CLI syntax is not hard-renamed in that sprint.
- Add canonical user-journey acceptance coverage and release/migration docs to the final sprint.

## Rejected or softened

- **Do not reorder M3 before M2.** M2's gates are intentionally broad drift checks over hand-maintained data. M3 may require a post-change revalidation of those gates, but that is cheaper and safer than delaying all enforcement until after the highest-risk IR work.
- **Do not swap M4 and M5.** Consolidating clone clusters before decomposition reduces the number of moving parts. The risk is real, so M4 now records clone/surface evidence before M5 starts.
- **Do not diversify vendors inside this chain.** A single `vendor: codex` keeps the run operationally simple. Independent model review remains useful as a preflight/checkpoint, but mixed-vendor execution is not necessary for this repo-local epic.
- **Do not add a full user-testing framework to this epic.** The user-testing idea is valuable, but it is larger than release hardening. Sprint 7 adds only the acceptance helpers needed to protect the canonical flow.
- **Do not invent new YAML schema keys for gates, budgets, or checkpoints.** The milestone docs now carry gates/artifacts so the chain runner is less likely to reject unknown YAML fields.

## Net shape

The spine was later split from 7 runnable milestones into 10, after applying the
`megaplan-decision` sizing rule that each sprint should have one coherent risk
surface and one profile decision. The current spine is:

1. Build correctness nets.
2. Build the offline consistency gate.
3. Delete stale node-spec code and hand off schema-provider evidence.
4. Fix IR/runtime seams.
5. Consolidate duplicate helper implementations.
6. Introduce schema-driven node classification.
7. Decompose behind the nets.
8. Unify runtime/session behavior.
9. Add RunPod as a hardened runtime session.
10. Finish plugin/verb semantics and release hardening.

The main change is that the plan is now more explicit about evidence, handoff, and user-visible acceptance rather than relying on milestone titles to carry those obligations.

## Split + resize pass

After the balance/overengineering review, the broadest phases were split and
resized:

- Old M2 became `m2a-consistency-gate` (`partnered/full/medium @codex`) and `m2b-node-spec-schema` (`partnered/thorough/high +prep @codex`).
- Old M4 became `m4a-dedup-helpers` (`directed/full/medium @codex`) and `m4b-schema-classification` (`partnered/thorough/high +prep @codex`).
- Old M6 became `m6a-runtime-factory` (`partnered/thorough/high +prep @codex`) and `m6b-runpod-session` (`premium/thorough/high +prep @codex`).

The split keeps cheap/mechanical work out of premium runs while preserving
premium rigor for kernel-breaking correctness work, IR contract changes, secrets,
GPU spend, and RunPod teardown safety. Sprints whose decisions were narrowed by
the review/prep passes use `partnered` rather than `premium`.

## Second fresh-eye pass

A second batch of ten DeepSeek V4 Pro reviews looked both outside the epic scope and back inside the revised scope. The raw results are under `out/subagent_reviews/excellence_epic_fresh/results/`.

Additional changes accepted:

- M1 now requires a heterogeneous golden-JSON oracle lane so the parity harness is not only checking the emitter through its own canonicalizer.
- M2 now covers model-asset integrity metadata, staged-model verification, and `asset_manifest.json` freshness/retirement, not just template/index drift.
- M3 now verifies the package version/release foundation before changing public APIs.
- M4 now requires all substring-classification sites to route through the central classifier seam, even if some internals remain centralized fallbacks.
- M5 now explicitly reruns M4 clone/classification checks and treats CLI JSON shape compatibility as behavior.
- M6 now specifies the `VibeSession` protocol, model/RunPod preflight, real RunPod smoke evidence or explicit escalation, and recorded/real payload coverage for runtime/eval bugs.
- M7 now verifies packaging/version/entrypoint/release surface, documents plugin/scratchpad trust boundaries, and groups deferred debt by category with severity and a proposed owning follow-up.

Additional recommendations rejected or deferred:

- Full plugin sandboxing/signing, pip hash enforcement, and git signature verification are real supply-chain concerns but too large for this epic. They are named follow-up security work.
- Full run-history/debuggability UX (`runs list`, `runs inspect`, retry lineage) is valuable but belongs in a separate observability sprint. This epic only requires structured failure/`next_action` behavior where it touches new or changed JSON commands.
- A large user-testing framework remains out of scope; only acceptance helpers needed by this epic should be added.

## Decision-lock passes

A third batch of ten DeepSeek V4 Pro reviews inspected each sprint for open questions, ambiguities, and low-level misses. A final targeted batch of five DeepSeek V4 Pro reviews then checked the remaining hard calls against the actual repository. Raw outputs are under:

- `out/subagent_reviews/excellence_epic_decision_lock/results/`
- `out/subagent_reviews/excellence_epic_final_lock/results/`

Decisions now locked into the sprint docs:

- `chain.yaml` uses relative `idea` paths, records the branch convention in comments, clarifies `auto_approve`, and adds prep for M6.
- M1 uses `tests/fixtures/failing_first_m1_corruptions.json` for the red-state corruption record and `tests/fixtures/golden_api_video_wan_i2v.json` for the heterogeneous API-JSON oracle.
- M2 gate lives at a new top-level `vibecomfy check` command, not `doctor`; existing CI workflows and pre-commit are real and named in the touchpoints.
- M3 targets `2.8.0` from current `2.7.0`, uses versioned release notes under `docs/release_notes/`, and defines the code-facing IR contract at `vibecomfy/contracts/ir.py`.
- M4 locks the exact `NodeClassification` dataclass shape, centralized unknown fallback, and clone detector command.
- M5 places shared runtime prompt execution in `vibecomfy/runtime/_execution.py::_execute_prompt()`.
- M6 locks the `VibeSession` protocol, `_RUNTIME_REGISTRY`, `RunResult.runtime`, `RunResult.timings`, `reconfigure() -> bool`, fake RunPod boundary, and `VIBECOMFY_RUNPOD_BUDGET_USD`.
- M7 locks plugin collision tiers, router ordering, distinct `image.edit` / `image.i2i` / `image.inpaint` semantics, `audio.t2a`, and the versioned release-note convention.

The final pass also corrected stale factual claims: `.github/workflows/` exists, `docs/api/m6-public-api.md` exists, the three stale node-spec files all exist, and `docs/release_notes/v2.7.0.md` is the current release-note convention.
- Some asset-link claims were imprecise (for example, hardlinks do not become dangling like symlinks), but the underlying integrity requirement was accepted.
