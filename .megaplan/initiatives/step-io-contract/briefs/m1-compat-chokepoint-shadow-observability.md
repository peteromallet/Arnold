# M1: Compat Chokepoint + Shadow Mode + Observability

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Install the single validation chokepoint and the de-risking machine that lets the contract roll out without bricking a live pipeline. This is the jury's #1 add and the core de-risking milestone: enforcement that goes big-bang would brick a real pipeline, so promotion to enforcement must be earned, per-seam, off telemetry.

Route artifact reads through ONE chokepoint at the disk⇄engine seam (`read_artifact_json`, `plan_repository.py:150`). Make reads lenient and writes strict, gated by the ARTIFACT's own `schema_version` (validate against the schema-in-effect-when-written, via m0b's registry). Enforce only when BOTH producer and consumer declare typed ports — gradual typing — so the 33 sites migrate incrementally and existing/frozen plans don't brick. Give every seam an `off → shadow (log-only) → warn → enforce` mode with violation telemetry (per-seam attribution + why-rejected diagnostics) that drives promotion.

## Scope

IN:

- A SINGLE validation chokepoint at the disk⇄engine seam (`read_artifact_json`, `plan_repository.py:150`), through which artifact reads pass and get validated via the m0b validator.
- Read-lenient / write-strict policy gated by the artifact's own `schema_version`: an old artifact is validated against its retained schema-in-effect-when-written (m0b registry), not today's schema, so frozen/in-flight plans stay readable on resume/status (`plan_repository.py:331`, `_core/workflow.py:376`).
- Gradual typing: enforce only when BOTH producer and consumer declare typed ports; otherwise loose pass-through. The 33 IO sites migrate incrementally, never one breaking flip.
- Seam identity = a 5-tuple port-binding crossing `(pipeline_id, producer_step, producer_port, consumer_step, consumer_port)`, keyed as `pipeline_id::consumer.port<=producer.port`. content_type / path / edge / phase are telemetry, NOT identity. The seam is derived at the chokepoint via a `binding_map` lookup (the binding_map is what M8a's authoring API reads/writes — seam-identity ≡ authoring API); a failed lookup means a legacy untyped read (seam `None`) that is never enforced.
- A per-seam mode machine `off → shadow (log-only) → warn → enforce`, settable per seam, defaulting to the safe end so no seam jumps straight to enforce. Mode state lives in a VERSIONED, pipeline-definition-scoped policy file `.megaplan/policies/step_io_contract_modes.json` (NOT state.json, which is run-scoped and doesn't scale), set via a small CLI.
- Gradual typing as ELIGIBILITY: `effective_mode = configured if both_sides_typed else min(configured, shadow)` — a seam with an untyped side can be shadow-observed but is never raised to enforce.
- `pipeline_id` stability is guaranteed by an explicit registry value (not a derived/positional id), with CI failing on a rename that lacks a migration.
- Violation telemetry: per-seam attribution + why-rejected diagnostics (from the m0b validator), recorded so a human can read what would have been rejected and decide to promote a seam's mode.
- Legacy artifacts lacking `schema_version` are classified as legacy/unknown and pass leniently, never crash and never counted as a hard violation.
- Tests: chokepoint validates on read; old-version artifact validates against retained schema; both-typed enforces, mixed-typed (one side untyped) is shadow-observed but never enforced per the eligibility rule; shadow logs without blocking; warn surfaces without blocking; enforce blocks; legacy artifact loads; per-seam mode set in the policy file survives across runs; seam ids are stable and unique across pipelines (CI rename guard).

OUT:

- No typed Ports wired onto the 9 stages yet (m2 declares produces/consumes); m1 provides the enforce-when-both-typed MECHANISM, m2 supplies the typed sides.
- No model-seam / degraded-mode work (m3).
- No migration of the load-bearing-5 or long-tail sites (m5/m6); m1 only makes their incremental migration safe.
- No new validator or registry (those are m0b; m1 consumes them).
- No suspension composition (m4).

## Locked Decisions

- Shadow → warn → enforce with violation observability is FIRST-CLASS in the chokepoint, landing before any enforcement, because a big-bang enforce flip bricks a real pipeline (jury's #1 catch that the dossier author missed).
- ONE validation chokepoint at the disk⇄engine seam (`read_artifact_json`, `plan_repository.py:150`).
- Read-lenient / write-strict, gated by the ARTIFACT's own `schema_version`; validate against schema-in-effect-when-written, schemas retained not mutated.
- Enforce only when BOTH producer and consumer declare typed ports — gradual typing; 33 sites migrate incrementally.
- Seam identity is the 5-tuple `(pipeline_id, producer_step, producer_port, consumer_step, consumer_port)`, keyed `pipeline_id::consumer.port<=producer.port`; content_type/path/edge/phase are telemetry, not identity. The seam is resolved at the chokepoint via the `binding_map` (the same map M8a's authoring API reads/writes); a failed lookup = legacy untyped read (seam `None`), never enforced.
- Per-seam mode lives in the VERSIONED, pipeline-scoped policy file `.megaplan/policies/step_io_contract_modes.json` (NOT run-scoped state.json), set via a small CLI.
- Gradual typing is an ELIGIBILITY rule: `effective_mode = configured if both_sides_typed else min(configured, shadow)` — an untyped side caps the seam at shadow.
- `pipeline_id` stability comes from an explicit registry value; CI fails on a rename without a migration.
- Mode is per-seam, with per-seam violation attribution; promotion is driven by telemetry, not flipped globally.
- Legacy artifacts without new metadata are classified unknown/legacy — never success-by-default, never a parse crash.
- DOGFOOD KILL-SWITCH (pre-mortem risk 4): because Arnold runs on its OWN engine, a validator bug that rejects the engine's own valid artifacts could wedge the self-hosted (dogfooded) engine irrecoverably. Two guards are FIRST-CLASS: (a) the engine self-validates its OWN artifacts under the new contract BEFORE a seam is allowed to promote to enforce — a seam cannot reach enforce until the engine has demonstrably round-tripped its own artifacts through the contract; and (b) a GLOBAL enforcement-OFF / read-lenient ESCAPE that drops every seam back to lenient reads regardless of per-seam mode, so a validator bug can never brick the engine — recovery is always available.

## Open Questions

- The telemetry sink/format (JSONL artifact, log stream, counters) and how promotion decisions are surfaced to an operator.
- Whether `read_artifact_json` is the only chokepoint or whether the write side needs a symmetric strict-validate entry point.
- How "both producer & consumer typed" is determined at the chokepoint before m2 has actually wired ports (capability probe vs. registry of typed sites).

## Constraints

- Frozen/in-flight plans must remain readable on resume/status — read leniency gated by the artifact's own version is the mechanism; a regression test must cover resume of a pre-contract plan.
- No seam may jump straight to enforce; the default must be safe (off/shadow).
- The chokepoint must not add a blocking cost in shadow/off mode beyond logging (m8 benchmarks the enforce path).
- Gradual typing must guarantee an un-migrated site (one side untyped) keeps working unchanged.
- Bases on m0a (type) + m0b (validator/registry); must not modify either.

## Done Criteria

1. Artifact reads pass through a single chokepoint at `read_artifact_json` (`plan_repository.py:150`) that validates via the m0b validator.
2. Reads are lenient and writes strict, gated by the artifact's own `schema_version`; an old-version artifact validates against its retained schema, and a test proves resume/status of a pre-contract plan still loads (`plan_repository.py:331`, `_core/workflow.py:376`).
3. Enforcement applies only when both producer and consumer are typed; a mixed (one-side-untyped) seam passes through unchanged; tests prove both.
4. Each seam has an `off → shadow → warn → enforce` mode; shadow and warn never block, enforce blocks; tests prove each mode's behavior.
5. Violation telemetry records per-seam attribution + why-rejected diagnostics, and a human-readable view of would-be-rejected violations is EMITTED as a queryable artifact; a test asserts the telemetry artifact exists, attributes a seeded violation to the correct seam, and carries its why-rejected diagnostic (the view is an operator-facing OUTPUT — promotion is exercised programmatically per criterion 11, never gated on a human reading it).
6. Legacy artifacts without `schema_version` are classified legacy/unknown and load leniently — not success-by-default, not a crash.
7. Per-seam mode is set in the versioned policy file `.megaplan/policies/step_io_contract_modes.json` (via the CLI) and survives across runs; a test proves a mode set in one run is honored in the next (not lost with run-scoped state).
8. A legacy untyped seam can be shadow-observed but is never enforced — the eligibility rule `effective_mode = min(configured, shadow)` when a side is untyped holds; a test proves an untyped-side seam configured to enforce stays at shadow.
9. Seam ids (the 5-tuple) are stable and unique across pipelines; a `pipeline_id` rename without a migration fails CI; a test/CI check proves the stability guard.
10. No stage ports, model-seam work, or site migrations are performed; behavior of un-typed seams is unchanged.
11. A validator bug cannot brick the engine: the global enforcement-off / read-lenient escape works (a test proves flipping it drops every seam to lenient reads and the engine recovers), and the engine validates its OWN artifacts before any seam promotes to enforce (a test proves a seam cannot reach enforce until the engine has round-tripped its own artifacts through the contract).

## Touchpoints

- `megaplan/plan_repository.py:150` (`read_artifact_json` — the chokepoint)
- `megaplan/plan_repository.py:331`, `megaplan/_core/workflow.py:376` (resume/status read paths that must stay legible)
- new per-seam mode + telemetry module (5-tuple seam identity; mode resolution via `binding_map` lookup)
- `.megaplan/policies/step_io_contract_modes.json` (versioned, pipeline-scoped mode policy file) + small mode-setting CLI
- `binding_map` (read here, authored by M8a) + explicit `pipeline_id` registry value + CI rename guard
- m0b validator + schema registry (consumed)
- m0a `ContractResult` / `schema_version` (consumed)
- chokepoint, gradual-typing-eligibility, mode-machine, policy-file-persists-across-runs, seam-id-stability/CI-rename-guard, telemetry, and legacy-read tests

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is the de-risking core of the whole epic and the jury's #1 add. If shadow/warn/enforce-with-observability and version-gated read-leniency are not right here, the first enforcement flip bricks a live or frozen pipeline. It is the safety substrate every downstream migration rides on, so it earns thorough/high.
