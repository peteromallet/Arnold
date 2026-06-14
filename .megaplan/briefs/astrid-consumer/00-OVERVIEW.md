# Arnold-side epic: host ASTRID as a first-class capability consumer

## What this epic is

ASTRID (a file-based toolkit for AI agents to make image / video / audio / timeline
art via a CLI gateway) integrates with Arnold by **importing Arnold** and registering an
Astrid `StepInvocationAdapter` in Arnold's existing `StepInvocationAdapterRegistry`. Astrid
is the next non-megaplan consumer of the step-io contract after C4's evidence-pack verifier.

This epic is the **Arnold-side** remainder needed so Astrid can host as a *media-producing*
consumer. It **RUNS AFTER the `step-io-contract-condensed` epic (C1–C4) completes** — its
PRECONDITION is a finalized, landed step-io contract on `arnold-generalized-pipeline`. It builds
ON that substrate; it does not rebuild it.

> **RE-GROUND PRECONDITION:** this epic was authored against a CHURNING tree — the arnold repo is
> concurrently running step-io, a `structural-decomposition` chain, AND m-series migration milestones
> that RELOCATE modules. So every `file:line` touchpoint below is **as-of-authoring and directional,
> not final**. Before AR1 runs, re-verify touchpoints against the LANDED HEAD (prep does most of this).
>
> **step-io status (mid-flight, near done):** C1 + C2 landed; C3 "suspend/resume + fan-out"
> done/landing (it lands the concrete `StepwiseDriver`); C4 "authoring API + acceptance gate"
> EXECUTING. This epic is
> SCHEDULED to start once step-io C1–C4 has finalized; everything below is written against the
> finalized contract step-io will have delivered.

Driving ticket: `01KTRQ63JY64RKFEPC87E7HR1A` (areas A–G). This epic distils the items that are
**genuinely new** Arnold work after step-io and drops everything step-io already delivers.

## Dependency / sequencing

- **Runs AFTER** `step-io-contract-condensed` C1–C4 + the arnold migration stabilize on
  `arnold-generalized-pipeline`. C1–C4 deliver: typed `ContractResult` + the 11-field
  `HumanSuspension` envelope (`types.py:617`; `Suspension` is an alias of it),
  executor port enforcement, the generic disk-seam chokepoint, the relocated + live
  model adapter (`kind="model"`), the concrete externally-drivable `StepwiseDriver` + opaque
  `ResumeCursorRef`, suspension-aware fan-out + composite-cursor persistence, the enforced
  authoring API (`reads`/`writes`/`invocation`) + `arnold pipeline check`, the acceptance gate,
  and the Arnold-native `evidence-pack` verifier (the 2nd consumer).
- The **Astrid-side** megaplan (the adapter impl, gateway `--engine arnold`, session-succession
  engine, orchestrator migration, retiring `task/`) runs in the **Astrid repo** and is NOT this
  epic. Different repo from step-io → no file collision, only the contract.

## What this epic judged ALREADY-DONE-BY-STEP-IO (and therefore is NOT here)

| Ticket area | Why it is already covered post-step-io |
|---|---|
| **A** — `StepInvocationAdapter` accepts a file-producing, non-LLM adapter | `step_invocation.py` registry already takes arbitrary `kind`s with no megaplan wiring; `replace_reserved`/`register` are generic; `StepContext.artifact_root` + `StepResult.outputs` + `ContractResult.evidence_refs` already give the path-based produces path. C2 only wires the `model` slot. → confirm + document (AR1 Part A, small), not net-new machinery. |
| **B** — typed media edges enforced via the authoring API | C4 already ENFORCES `reads`/`writes`/`invocation`; `ContentValidatorRegistry` (reference-metadata-only, `content_validation.py`) + `ContentTypeRegistry` (`types.py:CONTENT_TYPES`) + `EvidenceArtifactRef` (uri/content_type/digest/size — reference-by-metadata) all exist. → only **registering the media content-types** is new (AR1 Part A). |
| **C** — an external driver can drive the operator loop | C3 lands the concrete externally-drivable `StepwiseDriver` + the opaque `ResumeCursorRef` (`runtime/driver.py`, `runtime/resume.py:51`, `CONTRACT.md`). The generic resume surface is already plan_dir-decoupled. → DONE. |
| **E** (partial) — decision-string resume; unmatched-`next` halt | C3 delivers `human_input`→ctx decision resume; `routing.py` ALREADY raises `RoutingError` on an unmatched `next` (no silent halt) at the generic resolver. The dual-contract *extension* (AR2) and the journal cap (AR1 Part B) remain. |
| **F** (partial) — `decision_vocabulary` rule, `join_parallel_results` delegation, schema-hash round-trip | The mechanisms exist (`routing.py`, `hooks.join_parallel_results`, `CONTRACT_RESULT_SCHEMA_VERSION`); C4's `tests/m8` asserts them — but only inside the **test tree**, not as an importable package. → packaging is new (AR1 Part C). |

## What is GENUINELY-NEW Arnold work (this epic)

Three milestones. **AR1** bundles the whole additive Arnold-side surface a non-megaplan media
consumer (Astrid) binds against. **AR2** is the dual-contract suspension extension. **AR3** is an
OPTIONAL media cost model.

| # | Milestone | Ticket area | Why new post-step-io |
|---|---|---|---|
| AR1 | Consumer-readiness — media content-types + non-model adapter contract (Part A, prerequisite), `read_event_journal` streaming/paging (Part B), importable `arnold.conformance` suite (Part C, validates last) | A, B, E (journal), F | Register `video/mp4`, `audio/wav`, `application/x-astrid-timeline` (+ reference-metadata validators) and prove + document a non-LLM file-producing adapter rides the registry + typed edges (the stable public contract Astrid binds against); add additive streaming/paged journal readers beside the preserved eager API; lift the cross-consumer checks (`tests/m8`/`tests/arnold`) into an importable, megaplan-free `arnold.conformance` package the gate calls and Astrid runs. All additive. |
| AR2 | Dual-contract suspension: produces-re-verification on resume | D | C3 resumes a *decision* (`human_input`→ctx). The "run-dir is the edit surface" gate needs the resume payload to ALSO be a `produces` artifact the human EDITED, **re-verified through the chokepoint on resume** (incl. the AR1 media reference validator). C3 builds none of this. **Depends on AR1.** |
| AR3 | Media cost model (OPTIONAL) | E | `CanonicalUsage` is token-only and lives only in the megaplan-coupled module (`usage_pricing.py`; the generic `arnold/agent/agent/usage_pricing.py` is a shim re-export of it — no neutral usage type exists). Add a NEUTRAL `media_usage` record + per-media-unit pricing rows in generic `arnold/` so per-image / per-second-of-video / per-song cost is accountable, not opaque. Sourced from the AR1 non-model adapter. |

## Sizing table

| Milestone | Scope (one line) | Profile | Robustness | Depth | Size |
|---|---|---|---|---|---|
| AR1 | Consumer-readiness bundle: media content-types + non-model adapter contract (Part A, prereq) + `read_event_journal` streaming/paging (Part B) + importable `arnold.conformance` suite (Part C, last) | partnered | thorough | medium | ~2wk |
| AR2 | Dual-contract suspension extension — produces-re-verification-on-resume (the "run-dir is the edit surface" gate); depends on AR1 | premium | thorough | high | ~2wk |
| AR3 | Neutral `media_usage` record + per-media-unit pricing — **OPTIONAL**, additive | premium | thorough | high | ~2wk |

Total: **3 milestones**, each ≤ ~2 weeks. Order: AR1 → AR2 → AR3 (AR3 optional). `vendor: codex`,
`merge_policy: auto`, full robustness on the contract-touching milestones.

## What is explicitly OUT

- **Everything step-io C1–C4 delivers** (the table above): the `ContractResult`/`HumanSuspension`
  type, executor enforcement, the chokepoint, the model adapter + relocation, the concrete
  `StepwiseDriver` + `ResumeCursorRef`, suspension-aware fan-out + composite-cursor persistence,
  authoring-API enforcement, `arnold pipeline check`, the acceptance gate, the evidence-pack
  verifier. This epic CONSUMES them unchanged.
- **All Astrid-side work** (Astrid repo): the adapter implementation, `cas.py`/`inbox.py`
  extraction, `ExecutorRunResult` run-dir handle, `executor_version`, gateway `--engine arnold`,
  the session-succession engine, orchestrator migration, retiring `task/`.
- Decoupling the generic resume protocol from `plan_dir` (already decoupled — C3 finding).
- Any change to `ContractResult` / `HumanSuspension` / the schema registry / the validator / the
  mode-ladder semantics (frozen by the migration + C1).
- A media *content decoder* (we validate by reference/metadata only — the `content_validation.py`
  "blob-reference metadata shapes only" contract; never parse 2 GB of bytes at a seam).
