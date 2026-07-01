# M0b: Validator + Schema Registry

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Build the behavior that audits a `ContractResult` against a schema, and the registry that retains schema versions so an artifact can be validated against the schema that was in effect when it was WRITTEN. This is where the behavioral risk of the contract lives, so it is split out from the type (m0a).

Deliver the structural-type-audit validator: a single function that checks every field of a payload is in the declared schema and every type matches — closing the hallucinated-key and wrong-type holes that today's `validate_payload` (`workers/_impl.py:1853`, key-presence-only) ignores. Deliver the schema registry with version RETENTION: schemas are versioned and retained, never mutated in place, so read-lenient/write-strict in m1 can validate an old artifact against its own schema-in-effect-when-written rather than against today's schema.

This milestone provides the validation MECHANISM and the registry. It does not wire them into any seam, chokepoint, or enforcement path — m1 does that.

## Scope

IN:

- The structural-type-audit validator function: for a given payload + declared schema, assert every field is present in the schema and every value's type matches the schema's declared type. Return a structured result with per-field, why-rejected diagnostics (so m1's telemetry can attribute violations).
- Content-validators are PLUGGABLE, keyed by `content_type` (B3): JSON-Schema validates the manifest payload; a content-validator validates the REFERENCED blob (dims / codec / decodeability) — a separate, registered concern from validating the manifest. Provide the pluggable registration seam and a thin default; do NOT build exotic content-validators now.
- The always-on audit keeps ONLY a deterministic full-vs-manifest split BY SIZE plus a policy HOOK (B5 — the CUT). Do NOT bake `receipt` or `sampled` audit profiles: they weaken the validate-before-act promise and are NOT a one-way door, so they wait for real perf data. (Supersedes any prior "audit profile {full|manifest|receipt|sampled}" wording.)
- Schema versioning supports `logical_type` + an accepted_version_RANGE (B2-adjacent), not only exact-hash equality — an artifact written under one canonical hash may satisfy a consumer that accepts a version range over the same logical type.
- Make the audit a SINGLE uniform validation path with no per-tier branching — it is intended to run ALWAYS, including for wire-trusted enforced-mode results (cheap defense-in-depth), so it must be written to be tier-agnostic from the start.
- The schema registry: register a schema, retrieve a schema by `schema_version` (hash), and guarantee version RETENTION — registering a changed schema produces a NEW version and never overwrites an existing one. Schemas are stored as canonical JSON Schema, content-addressed at `<artifact_root>/.contract_schemas/sha256/<hash>.json` (immutable) plus an `index.json` mapping logical-name→version history; `schema_version = sha256:<hash of the CANONICAL schema>` (NOT the worker projection).
- Seed v0 schemas as legacy-lenient JSON Schemas (legacy required keys, `additionalProperties: true`) derived from `STEP_SCHEMA_FILENAMES` + `SCHEMAS`, so an existing/old plan still loads; new writes use strict v1+ (`additionalProperties: false`). The worker strict-mode schema (Codex `--output-schema`, Hermes `response_format`) is a PROJECTION of the canonical, not the canonical itself; `.megaplan/schemas/*.json` is "latest worker schema" only, NOT the historical registry.
- Resolve a `ContractResult`'s `schema_version` to the retained schema-in-effect-when-written for validation — resolution is by HASH first (version retention), never against today's latest.
- A projection-equivalence test: the worker strict-mode projection is equivalent to the canonical schema (guards dialect drift — OpenAI strict vs Hermes vs local).
- Tests covering: matching payload passes; hallucinated extra key rejected; wrong-type field rejected; missing field handled; old `schema_version` validates against its retained schema, not the current one; a v0 legacy-lenient schema lets an old plan still load.

OUT:

- No chokepoint wiring (`read_artifact_json`) — that is m1.
- No read-lenient/write-strict gating, no enforce-only-when-both-typed, no shadow/warn/enforce mode machine — m1.
- No violation TELEMETRY pipeline/promotion logic — m1 (the validator returns diagnostics; m1 consumes them).
- No changes to any stage, executor, handler, or worker.
- No model-seam degraded-mode logic (m3); the validator is the closer m3 reuses, but m3 owns the trust tiers.

## Locked Decisions

- The validator performs a STRUCTURAL-TYPE AUDIT (every field in schema, every type matches), not key-presence. This is the cheap universal closer for the holes `validate_payload` ignores.
- The audit is a single uniform path with no per-tier branching — designed to run always, even in enforced wire-trusted mode (defense-in-depth, uniform & bulletproof over minimal-redundancy).
- Schemas are versioned and RETAINED, never mutated in place; validation is against the schema-in-effect-when-written, keyed by the artifact's `schema_version` hash.
- `schema_version` is a schema HASH; a schema change yields a new retained version, never an in-place edit.
- Schemas are canonical JSON Schema. The registry is content-addressed at `<artifact_root>/.contract_schemas/sha256/<hash>.json` (immutable) + `index.json` (logical-name→version history); `schema_version = sha256:<hash of the CANONICAL schema>`, NOT the worker projection. Validation resolves by hash first (= version retention). `.megaplan/schemas/*.json` remains only the latest worker schema, not the historical registry.
- The worker strict-mode schema is a PROJECTION of the canonical; one canonical schema drives BOTH the worker projection AND the always-on structural audit. Projection-equivalence is tested to guard dialect drift.
- v0 schemas are seeded legacy-lenient (legacy required keys, `additionalProperties: true`) from `STEP_SCHEMA_FILENAMES` + `SCHEMAS` so old plans still load; new writes are strict v1+ (`additionalProperties: false`).
- Content-validators are PLUGGABLE, keyed by `content_type` (B3): JSON-Schema validates the manifest; a content-validator validates the referenced blob (dims/codec/decodeability), a separate registered concern. Ship the pluggable seam + a thin default; build no exotic content-validators now.
- The always-on audit keeps ONLY a deterministic full-vs-manifest split BY SIZE plus a policy HOOK. `receipt` and `sampled` profiles are explicitly CUT (B5): they weaken validate-before-act and are not a one-way door, so they wait for real perf data — they are NOT baked.
- Schema versioning supports `logical_type` + an accepted_version_RANGE, not only exact-hash equality (B2-adjacent); hash-first resolution remains for version retention, the range governs consumer acceptance.
- The validator imports the m0a type ONLY and adds behavior on top; it does not redefine or extend the frozen type.

## Open Questions

- How strict the type matching is on the structural axis (e.g. int-vs-float, optional/null handling, nested/recursive payloads, list element typing).
- The exact structured diagnostic shape the validator returns for m1 to attribute and render.
- Whether registry lookups are cached/memoized given the always-on audit on every seam crossing.

## Constraints

- The validator must be pure (no state mutation) so any reader/chokepoint can call it freely.
- The always-on uniform path must be cheap enough to run on every seam crossing without becoming a hot-path cost (m8 benchmarks this; design for it here).
- Registry version retention must never silently overwrite a prior schema version.
- Bases on m0a's frozen type; must not require any change to that type.

## Done Criteria

1. The structural-type-audit validator exists, takes a payload + declared schema, and returns a structured pass/fail with per-field why-rejected diagnostics.
2. The audit rejects hallucinated/extra keys and wrong-typed fields that key-presence validation (`workers/_impl.py:1853`) accepts today; tests prove each case.
3. The validator is a single uniform path with no per-tier branching and is safe to call in enforced mode (a test exercises the enforced-mode call).
4. The schema registry registers, retains, and retrieves schemas by `schema_version` hash; a schema change creates a new version and never overwrites an existing one.
5. A `ContractResult` with an OLD `schema_version` validates against its retained schema-in-effect-when-written, not the current schema; a test proves this.
6. The registry is content-addressed (`.contract_schemas/sha256/<hash>.json` + `index.json`) and immutable — a stored schema file is never overwritten; `schema_version` is the sha256 of the CANONICAL schema, not the worker projection; a test proves projection-equivalence.
7. An artifact validates against the schema-version it was written under even after the latest schema for that logical name has moved on (hash-first resolution); a test proves this.
8. A v0 legacy-lenient schema (`additionalProperties: true`) lets an old/pre-contract plan still load while new writes are strict v1+; a test proves both.
9. The validator is pure and mutates no state.
10. No seam, chokepoint, or enforcement path is wired; tests confirm runtime behavior elsewhere is unchanged.
11. Content-validators are pluggable and keyed by `content_type` (manifest JSON-Schema validation is separate from blob validation); a test registers a content-validator and proves it validates the referenced blob distinctly from the manifest. No exotic content-validators are built.
12. The always-on audit performs ONLY a deterministic full-vs-manifest split by size plus a policy hook; tests confirm no `receipt`/`sampled` profile exists.
13. Schema versioning supports `logical_type` + an accepted_version_range (not exact-hash-only); a test proves an artifact whose hash falls within a consumer's accepted range validates, while one outside the range does not.

## Touchpoints

- new validator module (structural-type audit) on the platform surface
- pluggable content-validator registry keyed by `content_type` (validates referenced blobs: dims/codec/decodeability), distinct from manifest JSON-Schema validation
- the always-on audit's full-vs-manifest-by-size split + policy hook (no `receipt`/`sampled` profiles)
- new schema registry module (versioned, retained; content-addressed `<artifact_root>/.contract_schemas/sha256/<hash>.json` + `index.json`; `logical_type` + accepted_version_range support)
- `STEP_SCHEMA_FILENAMES` + `SCHEMAS` (source of the v0 legacy-lenient seed); `.megaplan/schemas/*.json` (latest worker schema only, NOT the historical registry)
- `arnold/pipeline/types.py` (imports m0a `ContractResult` / `schema_version`)
- reference: `megaplan/workers/_impl.py:1853` (`validate_payload`, key-presence-only — the hole being closed)
- validator + registry tests (match, extra-key, wrong-type, missing-field, old-version-against-retained-schema, enforced-mode call, projection-equivalence, v0-lenient-loads-old-plan, content-addressed-immutability)

## Rubric

- Profile: `premium`
- Robustness: `thorough`
- Depth: `high`

Rationale: this is where the contract's behavioral risk concentrates — a validator that is too loose recreates the trust gap, and a registry that mutates schemas in place breaks every frozen/in-flight plan on resume. It must be correct before m1 turns it into a chokepoint, so it earns thorough/high; it sits one tier below m0a because it implements behavior over an already-frozen type rather than defining the irreversible abstraction.
