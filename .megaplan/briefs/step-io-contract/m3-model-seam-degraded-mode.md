# M3: Model Seam + Degraded Mode

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

The centerpiece, deliberately over-invested. m3 builds the MODEL ADAPTER of the `StepInvocation` seam defined in m2 — `render_step_message` IS that model adapter — NOT "the inbound chokepoint" as if model IO were the only seam. It is the model adapter of the invocation seam (the single inbound chokepoint FOR MODEL steps), one of {model, tool, human, state}; unknown adapter kinds fail closed (cross-ref m2). Take the step⇄model seam (and the engine⇄worker capability sub-seam) onto the contract, and make the degraded path — workers that cannot be given a structured-output schema — explicit, bounded, observable, and never trusted unless validated, without ever deadlocking a worker.

This is the acute pain and the proving ground that the universal contract holds even where the platform is weakest: Hermes gets ZERO structured output on execute/review because tools are always on (`hermes.py:1276`, `response_format` disabled when tools active), Shannon never passes a `--json-schema` (always prompt-only), and Codex `--output-schema` (`_impl.py:2227/2325`) works fresh/read-only but not on resume. A strict envelope would deadlock Shannon (all), Hermes-execute, and Codex-resume. The answer is two-tier trust with an always-on structural audit, proven on the riskiest stage: execute.

## Scope

IN:

- Two-tier trust:
  - Enforced/wire-trusted mode where the worker accepts a schema (Codex `--output-schema` fresh/read-only at `_impl.py:2227/2325`; Hermes `response_format` where tools are off and the model supports it).
  - Non-enforced mode (Shannon always; Hermes-execute where tools force `response_format` off at `hermes.py:1276`; Codex-resume) where the schema is delivered as a PROMPT TEMPLATE and the output is closed by the structural-type audit.
- An ALWAYS-ON structural-type audit (m0b validator) on the output of BOTH tiers — a single uniform validation path, no per-tier branching — so a hallucinated key or wrong-typed field is caught even on a wire-trusted result.
- `render_step_message` (serialize-in) IS the MODEL ADAPTER of the m2 `StepInvocation` seam: assemble the model-facing message with data-by-reference (large refs by tool, not inlined) and a token budget computed with REAL per-model-family tokenizers, keyed off `resolve_model`'s normalized string, via a local-first per-family table: tiktoken `o200k_base` for GPT/Codex; HF `AutoTokenizer` for DeepSeek/Kimi/GLM where installable; a conservative byte-estimate fallback `ceil(utf8/3) + 20-25%` (CJK-safe) otherwise. It accounts for tool-manifest + large_refs overhead and FAILS at assembly time (before dispatch) when over budget. In enforced mode an unknown family fails CLOSED; in non-enforced mode it fails SAFE (over-estimate + degraded telemetry). Unknown adapter KINDS (non-model) fail closed at the m2 registry, not here.
- The model adapter's budget must include MEDIA budgets — frame count, image resolution, audio seconds, file size — not only text tokens, so a vision/multimodal model input is budgeted correctly (an image/video/audio reference consumes a media budget, not just its serialized token cost).
- **Bounded advisory-evidence projection at the SOURCE (a token budget alone does NOT close this — it would just fail earlier or wrap the same noise).** Large execute "deviation"/audit file-path lists are materialized uncapped as prose and pasted forward: `megaplan/execute/quality.py:499` (`", ".join(unclaimed_changes)`), `megaplan/execute/aggregation.py:258` (`sorted(drift.files_added)`), then re-inlined into the NEXT batch prompt with no cap at `megaplan/prompts/execute.py:614` (rendered `:674`). Cap+sample these (emit `"<N> paths (showing K): … — full set via ArtifactRef"`) BEFORE they enter the batch artifact and BEFORE re-inlining. Proof-case: a real 337-file rename produced a 225,059-char execute prompt that was **77.5% (173,934 chars) advisory changed/unclaimed file-path lists** (two strings of 77K + 90K), with the actual current task at 0.4% — the literal embodiment of the "advisory evidence serialized as prose and pasted forward" thesis. This makes the source side reference-oriented so `render_step_message`'s budget operates on signal, not noise.
- **Semantic bulk-change summary + typed routable rework-target (the deeper half — fixes a NON-CONVERGENCE, not just bloat).** Two coupled additions, proven needed by a real 337-file rename milestone that span-spun in the execute↔review rework loop and never reached `done`:
  (1) *Semantic summary*: when a batch is a provably-uniform mechanical operation (one transform applied across N files — rename/move/import-rewrite), represent it to the model as the OPERATION — `rule + scope + manifest ArtifactRef + sampled deviations + tools to grep/read the live tree` — NOT enumerated per-file edits. The summary may be CHEAP/heuristic (GitHub-style: content-hash rename detection, path/extension patterns) BECAUSE correctness is verified against GROUND REALITY via tools, not trusted from the summary (the grounding lives in Evidence-First m4/m6 — review/execute check the actual current files, e.g. `grep` for residual `from megaplan.`, rather than serialized deviation claims). Conservative-only: collapse a change to "mechanical" ONLY when provably uniform, else fall back to per-edit (mis-collapsing substantive logic would hide review surface).
  (2) *Typed routable rework-target*: a review rework_item MUST reference a target kind execute can route — `{task_id | bulk_operation | manifest}` — closing the confirmed CONTRACT MISMATCH where review emits `task_id:"REVIEW"` (`megaplan/prompts/review.py:991`) for global/flag findings but execute only routes rework whose `task_id` exists in `finalize.json` (`megaplan/execute/batch.py:1341-1371`), so `"REVIEW"` → unrunnable → `unroutable_review_rework_mixed` (`batch.py:1599/1754`) → infinite spin. A cross-cutting bulk change's review findings (global rule failures) currently have NO task to attach to; a `bulk_operation`/`manifest` rework target gives them a routable owner. This is the literal "stringly-typed seam" the epic exists to kill: two contracts (review-output, execute-routing) disagreeing about what `REVIEW` means.
- `render_step_message` is the SINGLE INBOUND CHOKEPOINT FOR MODEL STEPS (the model adapter of the m2 invocation seam, not the only seam): every OWN model-facing prompt is assembled through it, so the token budget is unavoidable (not an opt-in each site must remember to call — the scattered-`validate_payload` disease one level up). The budget is computed on the FULL assembled model input (system + history + prompt + tool results), NOT a single prompt string — the confirmed Hermes gap is the template for the whole multi-turn class: `run_conversation` concatenates `conversation_history` + `user_message` + system into `api_messages` while only the bare prompt is checked today (`hermes.py:1172/1200`). A coverage swarm + closure proof produced the CLOSED catalog of assembly sites (see dossier "RESOLVED — prompt-assembly coverage"); the OWN-UNGUARDED sites m3 must route through the chokepoint are: the resident loop (`resident/agent_loop.py`, `resident/runtime.py` — multi-turn, currently zero budget check), Hermes combined prompt+history (`hermes.py:1078/1425`) and its summary/repair follow-ups (`797/899/917`), and the shared JSON-repair builder (`_impl.py:1575`) when Hermes calls it. The budget check for the Hermes multi-turn path belongs IN `run_conversation`/`run_agent` where the pieces become `api_messages`.
- `capture_step_output` (validate-out): parse → typed `ContractResult`, schema-validate, and PRESERVE the Codex repair loop (one-shot json-repair) and `_recover_codex_payload`'s 3 fallbacks where they apply.
- Degraded modes are explicit, bounded, observable (telemetry says which tier ran and why), and NON-AUTHORITATIVE unless the structural audit passes. No worker is made unusable; none is left untrusted.
- No worker deadlocks: Shannon/Hermes are NOT forced into a repair loop (cost); the structural audit is the cheap universal closer instead. When a non-enforced output fails the audit, the bounded retry is exactly ONE repair re-ask (envelope-only, no tools / no redo) → terminal `worker_structural_audit_failed`; the hard ceiling is 2 model turns, which guarantees no deadlock. This unifies the Codex and Shannon repair paths.
- Prove the whole thing on EXECUTE first — the riskiest stage (2000+ line prompt, batch-relaxed validation, checkpoint recovery, rework loops, Hermes-no-structured).

OUT:

- Migration of finalize/critique/review/gate (m5) and the long tail (m6); m3 does execute as the vertical proof, others follow.
- The `human_review` verb / resume UX / who-answers routing (features on top of m4's suspension primitive).
- Budgeting accumulation INSIDE an external/vendored session — `codex exec resume` rollout history (`_impl.py:2228`), Shannon/Claude tmux transcript (`shannon.py:2192/2358`, `vendor/shannon`), pure process-spawn (`runtime/process.py`). This is the `DONT_TOUCH` side of the boundary: we budget what WE assemble before handoff; what accumulates behind a vendored CLI is handled by the existing session rotation/compaction (e.g. Codex token-headroom rotation `_impl.py:2160`, Shannon `/compact`), which m3 must leave intact and observable but does NOT replace. We do not claim to budget what we cannot see — that honesty is the boundary. Trivial fixed launcher/control turns (`shannon.py:2083/2197/2359`) that point at an already-checked file or send a tiny fixed prompt are noted but not forced through the chokepoint.
- Suspension-aware composition itself (m4); m3 emits a `ContractResult` with `status`, but cross-step propagation is m4.
- Authoring-API enforcement (m7).
- Any change to the validator/registry/chokepoint internals (consumed from m0b/m1).

## Locked Decisions

- m3 builds the MODEL ADAPTER of the `StepInvocation` seam defined in m2 — `render_step_message` IS the model adapter — NOT "the single inbound chokepoint" as if model IO were the only seam. It is the model adapter of the invocation seam (the single inbound chokepoint FOR MODEL steps), one of {model, tool, human, state}. Unknown (non-model) adapter kinds fail closed at the m2 registry (cross-ref m2).
- The model adapter's token budget must include MEDIA budgets (frame count, image resolution, audio seconds, file size), not only text tokens, so a vision/multimodal model input is budgeted correctly.
- Two-tier trust: enforced wire-trust + non-enforced prompt-template-plus-structural-audit. No worker is unusable; none untrusted.
- The structural-type audit runs ALWAYS, including in enforced mode — uniform single validation path, no per-tier branching (defense-in-depth; uniform & bulletproof over minimal-redundancy).
- Do NOT force a repair loop on Shannon/Hermes (cost); the structural audit is the universal closer. The bounded retry is exactly ONE repair re-ask (envelope-only, no tools/redo) → terminal `worker_structural_audit_failed`; hard ceiling of 2 model turns = no deadlock; this unifies Codex + Shannon repair.
- Token budget uses real per-model-family tokenizers via a local-first table — tiktoken `o200k_base` (GPT/Codex), HF `AutoTokenizer` (DeepSeek/Kimi/GLM where installable), conservative byte-estimate `ceil(utf8/3)+20-25%` CJK-safe fallback — keyed off `resolve_model`'s normalized string; fails at assembly time before dispatch; accounts for tool-manifest + large_refs overhead. Fail CLOSED on unknown family in enforced mode; fail SAFE (over-estimate + degraded telemetry) in non-enforced mode.
- Large data crosses by reference (by tool), not inlined into the prompt.
- `render_step_message` is the SINGLE inbound chokepoint FOR MODEL STEPS (the model adapter of the m2 invocation seam, not the only seam) for OWN prompt assembly; the budget runs on the FULL assembled model input (system + history + prompt + tool results), never a single prompt string. Boundary rule: we guard text WE assemble before handoff (OWN); accumulation inside a vendored/external session is `DONT_TOUCH`, covered by existing rotation/compaction. The coverage catalog is CLOSED (swarm + Codex closure proof, no live orphan); future dispatch sites must not bypass the chokepoint.
- Preserve `_recover_codex_payload`'s 3 fallbacks and the Codex one-shot json-repair; preserve execute's batch-relaxed validation as a native contract mode rather than the fuzzy `_normalize_worker_payload` path (that deletion lands in m5).
- Degraded output is explicit, bounded, observable, and non-authoritative unless validated.
- DONT_TOUCH TRIPWIRE (pre-mortem risk 6): a declared-out-of-scope vendored/external boundary cannot silently rot into an uncovered hole. A sentinel test FAILS if the vendored/external boundary MOVES — e.g. Shannon starts passing `--json-schema`, Hermes-execute stops disabling `response_format` when tools are active, or codex changes its session/resume model — so when the boundary shifts under us, the test fires instead of leaving the moved surface silently unbudgeted. A sensor sits exactly where we stopped looking.
- Prove on execute first (riskiest; Hermes-no-structured).

## Open Questions

- How the prompt-template schema delivery is rendered for non-enforced workers (inline JSON schema, worked example, or both) to maximize first-pass structural validity.
- How execute's batch-relaxed validation is expressed as a native contract mode (per-batch schema relaxation vs. a relaxed schema variant).
- Telemetry shape for "which tier ran, why degraded, audit result" so m1's observability surfaces it consistently.

## Constraints

- No worker may deadlock or hang waiting on a schema it cannot satisfy — Shannon, Hermes-execute, and Codex-resume must all complete.
- The structural audit must never be skipped on any tier.
- The token budget must fail loudly at assembly time, never silently overflow the model (the char→token motivating failure).
- A degraded/non-enforced output must not be treated as authoritative until the structural audit passes.
- Execute's existing checkpoint recovery, rework loops, and batch behavior must be preserved.
- Bases on m0a/m0b/m1/m2; must not modify the type, validator, registry, or chokepoint.

## Done Criteria

1. `render_step_message` assembles the model-facing message with large-refs-by-tool and a real per-model-family token budget (local-first table keyed off `resolve_model`'s normalized string) that FAILS at assembly time — before dispatch — when over budget (incl. tool-manifest + large_refs overhead); a test reproduces the char→token overflow and proves it now fails at assembly before any dispatch.
2. `capture_step_output` parses to a typed `ContractResult`, schema-validates, and preserves the Codex repair loop + `_recover_codex_payload` 3 fallbacks; tests cover each.
3. Two-tier trust works: an enforced-mode worker (Codex `--output-schema` / Hermes `response_format`) is wire-trusted; a non-enforced worker (Shannon, Hermes-execute, Codex-resume) gets the prompt-template path and is closed by the structural audit; tests cover both tiers.
4. The structural-type audit runs on BOTH tiers via the single uniform path; a wrong-typed/hallucinated-key output is rejected even from a wire-trusted worker (test).
5. No worker deadlocks: Shannon, Hermes-execute, and Codex-resume all complete without a forced repair loop; an audit-failing non-enforced output gets EXACTLY ONE repair re-ask (envelope-only) then terminates as `worker_structural_audit_failed`, bounded by the 2-turn ceiling; tests prove the single attempt and the bound.
6. An unknown model family fails CLOSED in enforced mode (budget refuses to assemble) and fails SAFE (over-estimate + degraded telemetry) in non-enforced mode; tests prove each.
7. Degraded output is observable (telemetry records tier + reason + audit result) and non-authoritative unless validated; a degraded-then-failed-audit output is not treated as done (test).
8. Execute is fully on the contract end-to-end (assembly → output capture → validation) with checkpoint recovery, rework loops, and batch relaxation preserved; the first-key-valid-parse motivating failure is reproduced and now caught (test).
9. The OWN-UNGUARDED sites from the closed coverage catalog now route through `render_step_message`: the resident loop (`resident/agent_loop.py`, `resident/runtime.py`), Hermes combined prompt+history (`hermes.py:1078/1425`), Hermes summary/repair follow-ups (`797/899/917`), and the JSON-repair builder under Hermes (`_impl.py:1575`). A test proves the Hermes COMBINED input (system + history + prompt) is budget-checked — not just the bare prompt — reproducing the multi-turn-accumulation overflow and showing it now fails at assembly.
10. A COVERAGE-AUDIT test enforces closure structurally: it enumerates model-dispatch sites and FAILS if any OWN dispatch assembles a prompt without routing through `render_step_message` — so a future pipeline cannot silently reintroduce the hole. External/vendored session accumulation (`codex resume`, Shannon tmux) is asserted OUT of scope and left to its existing rotation/compaction (intact + observable).
11. `render_step_message` is the MODEL ADAPTER of the m2 `StepInvocation` seam (not a standalone chokepoint); a non-model adapter kind fails closed at the m2 registry (cross-ref test). The model adapter's budget includes MEDIA budgets (frame count, image resolution, audio seconds, file size), not only text tokens; a test proves a multimodal/vision input is budgeted on its media dimensions and fails at assembly when over a media budget.
12. A DONT_TOUCH boundary tripwire exists: a sentinel test FAILS if the vendored/external boundary moves (e.g. Shannon begins passing `--json-schema`, Hermes-execute stops disabling `response_format` under tools, or codex changes its session/resume model), so a declared-out-of-scope boundary cannot silently rot into an uncovered hole.

## Touchpoints

- `megaplan/workers/_impl.py:2227`, `:2325` (Codex `--output-schema`)
- `megaplan/workers/hermes.py:1276` (Hermes `response_format` disabled when tools active)
- Shannon worker path (no `--json-schema`; prompt-only)
- `_recover_codex_payload` + Codex json-repair loop
- `megaplan/workers/_impl.py:1853` (`validate_payload` — superseded here by the structural audit) and execute's batch-relaxed validation
- `megaplan/handlers/execute.py` (the proving-ground stage)
- new `render_step_message` / `capture_step_output` model-seam modules — `render_step_message` IS the MODEL ADAPTER of the m2 `StepInvocation` seam (registered as the model adapter kind; unknown kinds fail closed at the m2 registry) + local-first per-family tokenizer table (tiktoken `o200k_base`; HF `AutoTokenizer`; byte-estimate fallback), keyed off `resolve_model`'s normalized string, with MEDIA budgets (frame count / image resolution / audio seconds / file size) alongside text tokens
- the one-shot envelope-only repair re-ask path (unifying Codex + Shannon) with terminal `worker_structural_audit_failed` and 2-turn ceiling
- OWN-UNGUARDED coverage sites to route through the chokepoint: `megaplan/resident/agent_loop.py` (`:169/177/217`), `megaplan/resident/runtime.py` (`:148/171`), `megaplan/workers/hermes.py` (`:1078/1425` combined history, `:797/899/917` follow-ups), `megaplan/agent/run_agent.py` (`run_conversation` — where history+prompt+system become `api_messages`; the combined-budget check lives here), `megaplan/workers/_impl.py:1575` (JSON-repair builder under Hermes)
- DONT_TOUCH boundary (leave intact + observable, do NOT re-budget): `_impl.py:2160/2228` (Codex session rotation/resume), `shannon.py:2192/2358` + `vendor/shannon` (tmux transcript), `runtime/process.py` (spawn)
- the coverage-audit test (fails if an OWN dispatch bypasses `render_step_message`)
- m0b validator (always-on audit), m1 telemetry
- model-seam tests (two-tier, no-deadlock, one-repair-then-terminal, fail-closed-unknown-family, fail-safe-non-enforced, token-budget-fails-before-dispatch, structural-audit-catches, execute end-to-end)

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the deliberately over-invested centerpiece — the model seam is the acute pain, and degraded mode is where a naive strict envelope deadlocks workers or recreates the trust gap. It is proven on execute, the single riskiest stage. The two-tier trust design, always-on audit, real-tokenizer budget, and no-deadlock guarantee are the hardest correctness surface in the epic, so it earns thorough/high.
