# AR1: Consumer-readiness — media content-types + non-model adapter contract, event-journal streaming, importable conformance suite

**Milestone id:** `AR1-consumer-readiness` · **Profile:** `partnered` · **Robustness:** `thorough` · **Depth:** `medium` · **Vendor:** `codex` · **Repo:** Arnold (`arnold-generalized-pipeline`, C1–C4 landed)

One ~2-week consumer-readiness sprint with three additive parts that together form one coherent deliverable: the Arnold-side surface a non-megaplan media-producing consumer (Astrid, the 3rd consumer) binds against. All three are ADDITIVE and touch no frozen contract type.

**Internal sequencing within AR1:** (a) Part A, the adapter-contract, is the PREREQUISITE — register media content-types + reference validators and prove/document the non-model file-producing adapter FIRST, because both the later parts and the external consumer bind against it; (b) Part B, event-journal streaming, is independent and bounded (do it any time); (c) Part C, the conformance package, VALIDATES LAST — it packages the cross-consumer checks the adapter contract must satisfy and re-expresses the C4 gate to call them, so it is the natural closing step.

Covers ticket areas **A** + residual **B** (part a), the journal-memory item of **E** (part b), and **F** (part c).

---

## Part A (PREREQUISITE) — Media content-types + non-model file-producing adapter contract proof

The small, additive entry: it does NOT build new seam machinery; it registers the media content-types the registries already accept and proves + documents that a non-LLM, file-producing capability rides the existing adapter + typed-edge substrate.

### A. Outcome
Arnold ships first-class media content-types and a documented, test-proven path for a **non-model** `StepInvocationAdapter` that runs an external capability writing files under a caller-controlled output dir and returns path-based produces — without touching the model/prompt/token machinery (C2's model seam). After this part, Astrid can register its adapter against a stable, documented contract and declare typed media edges that validate by reference/metadata.

### A. Scope
IN:
- **Register the media content-types** alongside the existing builtins (`arnold/pipeline/types.py:497-508`, `_BUILTIN_CONTENT_TYPES` / `CONTENT_TYPES`): at minimum `video/mp4`, `audio/wav`, and `application/x-astrid-timeline`. Today only `text/markdown`, `image/png`, `application/x-git-diff`, `application/x-fanout-results+json` are registered. Each gets a schema object registered through `ContentTypeRegistry.register` so its content-addressed digest is available for typed-seam validation.
- **Register reference-metadata validators** for the media types in a `ContentValidatorRegistry` (`arnold/pipeline/content_validation.py`) — "blob-reference metadata shapes only" (validate `content_type` / `size_bytes` / `digest` / `uri` shape on the caller-provided `EvidenceArtifactRef` metadata; NEVER parse the bytes). Provide a small set of shared media validators and a documented way for a consumer to register its own (the timeline type is Astrid-specific shape — provide the hook, ship a permissive default).
- **Prove the non-model adapter path end-to-end** with a deterministic, model-less fixture adapter (NOT Astrid's real `run_executor`; a tiny in-repo fake that writes a file): a stage with `invocation = StepInvocation.with_adapter_config(kind="capability", adapter_config=...)` is registered in `StepInvocationAdapterRegistry.register("capability", ...)`, runs writing a file under `ctx.artifact_root`, and returns a `StepResult` whose `outputs` carries the path and whose `contract_result.evidence_refs` carries a typed `EvidenceArtifactRef` (content_type = one of the new media types). The handoff validates through C1's executor seam + the reference-metadata validator, NOT through the model adapter.
- **Document the adapter contract as a stable public surface**: a docstring + a short doc section on the `StepInvocationAdapter` Protocol (`arnold/pipeline/step_invocation.py:77`), the registry contract (`register` for a new `kind`, `resolve` fail-closed, `registered_kinds`), and the produces convention (path in `outputs` + typed `EvidenceArtifactRef` in `contract_result.evidence_refs`; out-XOR-project). State that a non-megaplan consumer registers with NO megaplan-specific wiring.

OUT:
- Astrid's real adapter implementation, `run_executor` wrapping, CAS identity-digest — Astrid-side.
- Any model/prompt/token path (C2) — the media adapter bypasses it; AR1 only asserts the bypass.
- Authoring-API *enforcement* of the edges (C4 already did it) — AR1 only registers the types the enforcement consumes and adds a media reference validator.
- A media content *decoder* — validation is by reference/metadata only.

### A. Locked decisions
- Media types are registered ADDITIVELY next to the existing builtins; no existing type changes.
- Validation is **by reference/metadata only** — the `content_validation.py` contract ("blob-reference metadata shapes only"). A 2 GB video is never byte-parsed at a seam.
- The non-model adapter `kind` is a free string registered via the existing `StepInvocationAdapterRegistry.register`; `"model"` stays reserved/handled by C2. No subclass zoo — one generic kind, parameterised by `adapter_config`.
- Produces convention: file path in `StepResult.outputs`; typed pointer in `ContractResult.evidence_refs` as an `EvidenceArtifactRef`. The adapter is a projector.

### A. Open questions
- Whether `application/x-astrid-timeline` ships a real JSON-Schema here or only a placeholder descriptor + a consumer-registration hook (the concrete timeline schema is Astrid-owned). **Default: ship the placeholder descriptor + a consumer-registration hook (the concrete timeline schema stays Astrid-owned); refine in-milestone only if it fails.**
- Whether the media validators belong in a new `arnold/pipeline/media_content.py` or extend `content_validation.py` directly (keep `content_validation.py` generic; a media module that *registers into* a `ContentValidatorRegistry` reads cleaner). **Default: proceed with a new `arnold/pipeline/media_content.py` that registers into the `ContentValidatorRegistry`, keeping `content_validation.py` generic; refine in-milestone only if it fails.**
- Whether to add a `requires-image-decoder` / `requires-video-encoder`-style capability string to the documented `required_capabilities` vocabulary so `arnold pipeline check` (C4) can verify media-capability satisfiability — or leave that to the consumer. **Default: leave media-capability satisfiability to the consumer for AR1 (do not add the capability string); refine in-milestone only if it fails.**

### A. Constraints
- No `megaplan` import in any new generic module; keep the executor's "no forbidden vocabulary" invariant.
- Do not modify `ContractResult` / `EvidenceArtifactRef` / `HumanSuspension` / the schema registry.
- The registered media types must round-trip through `ContentTypeRegistry.get` (digest stable) and a typed edge declaring one must pass C4's `arnold pipeline check`.
- Additive only: an existing pipeline with no media types still builds and runs unchanged.

### A. Done criteria
1. `video/mp4`, `audio/wav`, `application/x-astrid-timeline` are registered in the content-type registry; `CONTENT_TYPES.get(<each>)` returns a stable digest; a test asserts each round-trips.
2. A `ContentValidatorRegistry` carries reference-metadata validators for the media types; validating a well-formed `EvidenceArtifactRef`-shaped metadata passes and a malformed one fails — WITHOUT reading any blob bytes (test).
3. A model-less fixture `StepInvocationAdapter` registered under a non-`model` kind runs end-to-end through the registry: writes a file under `ctx.artifact_root`, returns path-based `outputs` + a typed `EvidenceArtifactRef` in `contract_result.evidence_refs`, and the handoff validates through C1's executor seam + the media reference validator — never touching the model adapter (test asserts no model-path call).
4. The registry accepts the non-model adapter via `register(kind, adapter)` with NO megaplan-specific wiring; `resolve` of an unknown kind still fails closed (test).
5. The `StepInvocationAdapter` Protocol + registry contract + produces convention are documented as a stable public surface (docstring + doc section), explicitly stating the non-LLM, file-producing, reference-by-metadata path.
6. A typed media edge (a `Port`/`PortRef` with `content_type="video/mp4"`) declared on a stage passes `arnold pipeline check` (C4) — a test runs the static check green.
7. No change to `ContractResult` / `HumanSuspension` / the schema registry / the model seam; an existing non-media pipeline still builds and runs unchanged (test).

### A. Touchpoints
- `arnold/pipeline/types.py:497-508` (`_BUILTIN_CONTENT_TYPES` / `CONTENT_TYPES` — add media types)
- `arnold/pipeline/content_validation.py` (`ContentValidatorRegistry`, `no_op_content_validator` — add media reference-metadata validators / a media-content module)
- `arnold/pipeline/step_invocation.py:77/93/105/120` (`StepInvocationAdapter` Protocol + registry — documented as stable public contract; CONSUMED, not changed)
- `arnold/pipeline/types.py:556` (`EvidenceArtifactRef` — the produces pointer; CONSUMED)
- C4's `arnold pipeline check` (the typed-media-edge static check; CONSUMED — a test exercises it)
- a model-less fixture adapter + media-content-type / validator / adapter-path / pipeline-check tests

---

## Part B — `read_event_journal` streaming / paging hardening

Small, self-contained, independent of parts A and C. `read_event_journal` (`arnold/runtime/event_journal.py:226-250`) loads the ENTIRE `events.ndjson` into a list with no streaming, cap, or paging. It is not media-specific, but a media pipeline with large-binary artifacts emits many events and reloads the whole journal on every status/resume read — compounding into an unbounded-memory read.

### B. Outcome
The event journal can be read incrementally — streamed and/or paged by sequence number — so a consumer reading status on a long-running, event-heavy (media) pipeline does not materialize the whole journal in memory. The existing eager `read_event_journal` contract is preserved as the default (backward-compatible) path.

### B. Scope
IN:
- **A streaming reader**: a generator that yields parsed events one line at a time (lazy), so a caller can iterate without building the full list. Preserves the existing semantics (skip unparseable lines; the NDJSON file is append-only and seq-ordered on disk, so streaming in file order is seq order for the common case).
- **Seq-range / paging reads**: read events `since_seq` (tail-follow) and/or `[from_seq, to_seq)` windows + a `limit`, so a status reader can fetch only new events since its last cursor instead of re-reading the whole file. Implemented over the streaming reader.
- **Bounded sort**: the eager `read_event_journal` sorts the full list by `seq`. The streaming / paged paths must not require a full in-memory sort; document that on-disk order is seq order (the fcntl-locked monotonic append guarantees it) and only sort within a bounded page when a caller explicitly requests a sorted page.
- **Preserve the eager API**: `read_event_journal(artifact_root) -> list[dict]` stays exactly as is (same return, same skip-bad-lines, same sort) for existing callers; the new readers are additive.

OUT:
- Changing the WRITE path (`NdjsonEventJournal.emit`, the fcntl-locked monotonic seq, the sidecars) — untouched.
- Any store backend, projection, or event-kind classification — the journal stays mechanism-only / store-less (its stated invariant).
- A new event schema or `EventEnvelope` change.
- Astrid-side consumption of the streaming reader.

### B. Locked decisions
- **Additive, backward-compatible.** `read_event_journal` keeps its exact signature + behavior; streaming/paging are new functions, not a breaking change.
- **Mechanism-only.** No store/projection/kind coupling; the journal stays a pure file reader (its documented invariant). No `megaplan` import.
- **On-disk order is seq order.** The monotonic fcntl-locked append means streaming in file order is seq order for normal operation; a full re-sort is only needed for the explicit whole-file eager call, which is preserved.

### B. Open questions
- Whether to expose `since_seq` tail-follow as a separate function or a parameter on one paged reader (prefer one paged reader with optional `since_seq` / `from_seq` / `to_seq` / `limit`). **Default: proceed with one paged reader carrying optional `since_seq` / `from_seq` / `to_seq` / `limit`; refine in-milestone only if it fails.**
- Whether to memo the last byte offset for a `since_seq` cursor to avoid re-scanning the file prefix on each poll (a real win for a long-poll status loop) — or keep it simple (re-scan, filter) for v1 and note the offset-cursor as a follow-up. **Default: proceed with the simple re-scan/filter for v1 and note the offset-cursor as a follow-up; refine in-milestone only if it fails.**
- Whether any current eager caller should migrate to paging now, or all migration is deferred to the consumer (default: leave callers; ship the new readers). **Default: leave existing callers on the eager API and ship the new readers; refine in-milestone only if it fails.**

### B. Constraints
- `read_event_journal`'s signature, return type, skip-bad-lines, and sort behavior are unchanged.
- The write path + sidecars are untouched.
- No `megaplan` import; the journal stays mechanism-only.
- The streaming/paged readers must skip unparseable lines identically to the eager reader.

### B. Done criteria
1. A streaming reader yields parsed events lazily (a generator) without materializing the full list; a test asserts it yields the same events as the eager reader and skips bad lines identically, without building the whole list (e.g. asserts laziness via a large fixture).
2. A paged / seq-range reader returns events `since_seq` and/or within `[from_seq, to_seq)` with a `limit`; a test reads only new events after a cursor and asserts the window + limit.
3. The streaming/paged paths require no full in-memory sort; a test over an in-order fixture asserts the page is seq-ordered without a whole-file sort, and a caller-requested sorted page sorts only within the page.
4. `read_event_journal(artifact_root) -> list[dict]` is byte-for-byte unchanged (same return, skip, sort); an existing-caller regression test passes.
5. The write path, sidecars, and mechanism-only invariant are untouched; no `megaplan` import (test/inspection).

### B. Touchpoints
- `arnold/runtime/event_journal.py:226-250` (`read_event_journal` — preserved; the new streaming / paged readers added beside it)
- `arnold/runtime/event_journal.py:98-204` (`NdjsonEventJournal` write path + sidecars — CONSUMED unchanged)
- streaming / paging / since_seq / eager-regression / bad-line-skip tests

---

## Part C (VALIDATES LAST) — Importable conformance suite for the 3rd consumer

C4's acceptance gate + cross-consumer assertions live under the **test tree** (`tests/m8/`, `tests/arnold/`) — they are NOT importable or runnable by an external consumer. Astrid is the 3rd consumer (after megaplan and C4's evidence-pack verifier) and needs to import a conformance suite and run it against its OWN adapter + pipeline to assert it sits correctly on the contract. This part closes AR1: it packages the checks the Part A adapter contract must satisfy.

### C. Outcome
Arnold ships an importable `arnold.conformance` package (a real package under `arnold/`, not a `tests/` module) that any external consumer can import and run against its registered adapter + authored pipeline, asserting the cross-consumer contract: protocol conformance, `ContractResult` schema-hash round-trip (the tripwire), the "every routing-participating stage has a usable decision vocabulary" rule, and `join_parallel_results` delegating to `stage.join`. The existing `tests/m8` acceptance gate is re-expressed to CALL this importable suite (so the package and the gate cannot drift), and the evidence-pack verifier is run through it as the in-repo reference 3rd-consumer proof.

### C. Scope
IN:
- **An `arnold.conformance` package** with callable conformance checks (functions returning a structured pass/fail result + diagnostics, usable both as pytest assertions and as a programmatic API an external consumer calls). The checks:
  - **Adapter protocol conformance**: a registered `StepInvocationAdapter` satisfies the `step_invocation.py:77` Protocol (`runtime_checkable` `isinstance` + an `invoke` smoke over a fixture invocation), and the registry resolves it / fails closed on unknown kinds.
  - **`ContractResult` schema-hash round-trip** (THE tripwire): a consumer's `ContractResult`(s) round-trip through `to_json`/`from_json` against the live `CONTRACT_RESULT_SCHEMA_VERSION` (`types.py:815`) — a version skew fails loudly (the `from_json` mismatch raise is asserted).
  - **Decision-vocabulary rule**: every stage that participates in decision/override routing has a usable vocabulary so an unmatched `next`/decision raises `RoutingError` rather than silently halting. `routing.py` ALREADY raises on an unmatched signal — the conformance check ASSERTS that property holds for the consumer's pipeline (no stage routes on an undeclared key that would slip through), closing the `01KTPVTA` family at the consumer boundary.
  - **`join_parallel_results` delegation**: a `ParallelStage`'s join goes through `hooks.join_parallel_results` → `stage.join` (the executor calls it at `executor.py:665`); the check asserts the consumer's parallel stages delegate, not hand-roll.
- **Re-express the C4 acceptance gate to call the package.** The `tests/m8/test_acceptance_artifacts.py` + related checks that duplicate these assertions in the test tree should import + call the `arnold.conformance` functions, so the importable suite is the single source of truth and the gate cannot diverge from what an external consumer runs. (Fold, do not re-litigate the gate's scope.)
- **Run the in-repo reference 3rd consumer through it**: the C4 `evidence-pack` verifier (`arnold/pipelines/evidence_pack/`) is run through the importable suite as the canonical example + a regression that the suite passes a real non-megaplan consumer. (Astrid is the external 3rd consumer; evidence-pack is the in-repo stand-in so this part is provable without the Astrid repo.)
- **Document the consumer entry point**: how an external consumer imports `arnold.conformance`, passes its registry + pipeline(s), and runs the suite — the "Astrid runs this" path.

OUT:
- New contract assertions beyond what C4's gate already defines — Part C PACKAGES the existing cross-consumer checks; it does not invent new gate criteria.
- The C4 benchmark / seam-coverage matrix as a whole (those are the acceptance gate's perf + coverage artifacts, not per-consumer conformance) — Part C lifts the per-consumer protocol/round-trip/vocabulary/join checks, not the whole gate.
- Astrid's own conformance run (Astrid-side, against the imported package).
- Any change to `routing.py` / `ContractResult` / `join_parallel_results` semantics (CONSUMED).

### C. Locked decisions
- **A real package, not a `tests/` module.** `arnold.conformance` lives under `arnold/` and is importable by an external consumer; the test-tree assertions become callers of it.
- **Single source of truth.** The C4 acceptance gate's per-consumer checks call the package, so the importable suite and the gate cannot drift.
- **No new gate criteria.** Part C packages the four existing cross-consumer assertions (protocol, schema round-trip, decision-vocabulary, join delegation); it does not expand the contract.
- **Reference consumer = evidence-pack.** The in-repo 3rd-consumer proof is the C4 evidence-pack verifier; Astrid is the real external consumer and runs the same package from its repo.
- **No `megaplan` import** in the conformance package — it must be runnable by a non-megaplan consumer.

### C. Open questions
- The exact home + name (`arnold/conformance/` package vs. `arnold/pipeline/conformance.py`); a package reads cleaner given four distinct checks + a runner. **Default: proceed with an `arnold/conformance/` package; refine in-milestone only if it fails.**
- The result shape of a programmatic check (a structured `ConformanceResult` with per-check pass/fail + diagnostics) vs. raising — provide both: a programmatic result API and thin pytest assertion wrappers. **Default: provide both — a structured `ConformanceResult` programmatic API plus thin pytest assertion wrappers; refine in-milestone only if it fails.**
- How much of `tests/m8` genuinely belongs in the importable package vs. stays gate-only (the benchmark + seam matrix stay gate-only; the per-consumer checks move) — sized when the catalog is read at run time. **Default: move the per-consumer checks into the package and keep the benchmark + seam matrix gate-only; refine in-milestone only if reading the catalog at run time shows otherwise.**
- Whether the decision-vocabulary check needs a pipeline-walk helper (enumerate routing-participating stages) that also lives in the package. **Default: ship a pipeline-walk helper in the package to enumerate routing-participating stages; refine in-milestone only if it fails.**

### C. Constraints
- The package must not import `megaplan` and must be importable by an external consumer.
- The C4 acceptance gate must still pass after re-expression (it now calls the package) — no weakening of the gate.
- No change to `routing.py` / `ContractResult` / `join_parallel_results` / the schema-version computation.
- The schema-hash round-trip check must fail LOUDLY on a version skew (assert the `from_json` raise), not silently pass.

### C. Done criteria
1. An importable `arnold.conformance` package exposes callable checks (programmatic result API + pytest wrappers) for: adapter protocol conformance + fail-closed registry, `ContractResult` schema-hash round-trip (version-skew fails loudly), the decision-vocabulary rule (unmatched `next`/decision raises rather than silently halts), and `join_parallel_results`→`stage.join` delegation; a test runs each green against a fixture consumer and red against a seeded violation.
2. The package imports with NO `megaplan` dependency and can be invoked by an external consumer passing its registry + pipeline(s) (test imports + runs it from a megaplan-free context).
3. The C4 `tests/m8` acceptance gate per-consumer assertions are re-expressed to CALL the `arnold.conformance` functions; the gate still passes (no weakening), and a test asserts the gate path goes through the package (single source of truth, no drift).
4. The in-repo evidence-pack verifier (`arnold/pipelines/evidence_pack/`) passes the importable suite end-to-end as the reference 3rd-consumer proof (test).
5. The schema-hash round-trip check fails loudly on a deliberately skewed `schema_version` (asserts the `from_json` mismatch raise), proving the tripwire fires.
6. The consumer entry point (how Astrid imports + runs the suite against its own registry + pipeline) is documented.
7. No change to `routing.py` / `ContractResult` / `join_parallel_results` / schema-version computation (consumed unchanged).

### C. Touchpoints
- `tests/m8/test_acceptance_artifacts.py`, `tests/m8/test_outbound_coverage_catalog.py`, `tests/arnold/` (the C4 acceptance/conformance assertions living in the test tree — the per-consumer checks are LIFTED into the package; the gate calls it)
- new `arnold/conformance/` package (the importable suite — the genuinely-new code)
- `arnold/pipeline/step_invocation.py:77/93/120` (adapter Protocol + registry — the conformance check subject; CONSUMED)
- `arnold/pipeline/types.py:769-793` (`ContractResult.to_json`/`from_json`) + `:815` (`CONTRACT_RESULT_SCHEMA_VERSION` — the round-trip tripwire; CONSUMED)
- `arnold/pipeline/routing.py:114-143` (`RoutingError` on unmatched signal — the decision-vocabulary check asserts this property; CONSUMED)
- `arnold/pipeline/executor.py:665` + `arnold/pipeline/hooks.py` (`join_parallel_results` → `stage.join` — the join-delegation check; CONSUMED)
- `arnold/pipelines/evidence_pack/` (the reference 3rd consumer run through the suite)
- conformance-package / gate-re-expression / evidence-pack-passes / schema-skew-fails / megaplan-free-import tests

---

## Rubric (AR1 as a whole)

- Profile: `partnered`
- Robustness: `thorough`
- Depth: `medium`

Rationale: AR1 is the highest-stakes of the three milestones because it bundles the public adapter contract Astrid binds against (Part A) and the importable conformance gate that proves the contract (Part C). No novel contract design — the registries, the adapter Protocol, the typed-edge enforcement, `arnold pipeline check`, and all the conformance assertions already exist; AR1 registers media types + a reference validator, adds additive streaming readers, and packages the existing cross-consumer checks. So it earns thorough (full test of the fail-closed + bypass + pipeline-check + schema-skew-tripwire + eager-regression paths) at partnered/medium rather than premium — it is wide (three parts) but each part is mechanical/additive and bounded. Part A is the prerequisite; Part C validates last; Part B is independent and small.
