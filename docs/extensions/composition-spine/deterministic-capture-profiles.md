# M0 Deterministic Capture Profiles — V1 Scope Freeze

Date: 2026-07-02
Status: frozen (planning-only; no runtime implementation)
Milestone: M0 — Decisions, Fixtures, and Protocol V0

## Posture

This document freezes the V1 deterministic-capture profile list and defines the
required evidence and usable release examples for each. It is a **durable
planning artifact only**. No runtime source, SDK export, test, script, or config
file is created or edited by this milestone.

Downstream milestones (M2, M3b, M5) cite this document when they implement
target-path schema validation, live/bake execution, and the second composed
release example (EX-02). Expanding V1 deterministic capture beyond the four
profiles listed here requires a new decision record and release-example evidence
from the milestone requesting the expansion.

Source of record: `.megaplan/initiatives/reigh-extension-composition-spine-epic/prep.md`
lines 41–42 (capture constraints), lines 44–45 (edge vocabulary);
`.megaplan/initiatives/reigh-extension-composition-spine-epic/m0-decisions-fixtures.md`
Locked Decisions lines 4–6 (profile selection, event-table conversion gate) and
Constraints line 3 (no expansion without release-example evidence);
`docs/extensions/composition-spine/m0-decisions.md` Section 7 (profile summary)
and Section 4 (ownership boundaries).

## 1. V1 Deterministic Capture Profiles

Exactly four capture profiles are in V1 scope. No other profile is included.
Event-table conversion becomes executable only through graph-owned keyframe
patch operations after M2 target-path validation lands.

### 1.1 Seed Table

**Profile name:** `seed table`

**Semantics:** A fixed-seed capture table that records deterministic,
reproducible outputs keyed by a seed value. Given the same seed and input
parameters, the capture produces equivalent outputs on every evaluation.

**Required evidence:**

- A seed value uniquely identifies the capture.
- The capture table contains one or more rows, each mapping a seed input to
  deterministic output values.
- Output values are recorded with enough type and unit information for the
  consumer to interpret them without ambiguity.
- Round-trip evidence: applying the same seed to the same parameter path
  reproduces the same output values.
- The capture table is scoped to a target path (e.g., `effect-param` or
  `shader-uniform`) owned by a graph-authoritative contribution.

**Usable release examples:**

- EX-02 (Effect + Live Data + Bake, M5): when a live data source is baked, the
  resulting durable capture may use seed-table entries to replace live-sampled
  values with deterministic equivalents for export readiness.
- Any example that requires reproducible parameter automation across different
  preview/export sessions.

**Owning milestone for execution:** M3b (live binding and deterministic capture
execution) after M2 target-path validation.

### 1.2 Event Table

**Profile name:** `event table`

**Semantics:** An event-driven capture sequence that records timestamped events
with known event schemas. Each event carries a type discriminator and typed
payload. The event table preserves the temporal order of events and supports
lookup by time range and event type.

**Required evidence:**

- Every event has a timestamp, an event type discriminator, and a typed payload.
- The event schema is known at capture time; unrecognized or unknown event types
  are rejected or recorded with an explicit fallback discriminator rather than
  silently dropped.
- Time-range queries: consuming code can request events within a time window and
  receive only events in that range.
- Type-filter queries: consuming code can request events of a specific type
  within a time window.
- The event table is scoped to a target path owned by a graph-authoritative
  contribution.

**Usable release examples:**

- EX-02 (Effect + Live Data + Bake, M5): live data that arrives as timestamped
  events (e.g., webcam frame metadata, generated-frame steering signals) can be
  captured into an event table during bake, then replayed or reduced to
  parameter values through graph-owned keyframe operations.
- EX-03 (Transition + Agent-Produced Mask Material, M5): agent-session events
  that guided mask generation may be captured into an event table for
  provenance and diagnostics.

**M2 gate:** Event-table conversion to keyframe data becomes executable only
after M2 target-path validation. Before M2, event tables may be recorded but not
converted to graph-owned keyframe patches.

**Owning milestone for execution:** M3b (live binding and deterministic capture
execution) after M2 target-path validation.

### 1.3 Scalar Table

**Profile name:** `scalar table`

**Semantics:** A single-value capture table where each row records one scalar
value bound to a parameter or uniform. The scalar table is the simplest capture
profile: a flat mapping from parameter identity to a typed value, suitable for
parameters that do not vary over time.

**Required evidence:**

- Each row maps a target-path identity (e.g., `effect-param:intensity` or
  `shader-uniform:opacity`) to a single typed scalar value.
- The scalar type is known and preserved (number, boolean, string, or
  enumerated value).
- The table supports lookup by target-path identity.
- Round-trip evidence: writing a scalar value to a target path and reading it
  back through the capture table yields the same value.
- The scalar table is scoped to a target path owned by a graph-authoritative
  contribution.

**Usable release examples:**

- EX-01 (Clip + Shader + Shader-Uniform Keyframes, M4): individual shader
  uniform values that do not vary over time (e.g., a single blend-mode constant)
  may be recorded in a scalar table rather than as full keyframe curves.
- EX-02 (Effect + Live Data + Bake, M5): when a live data source provides a
  single snapshot value rather than a time series, the bake result may be a
  scalar table entry.

**Owning milestone for execution:** M3b (live binding and deterministic capture
execution).

### 1.4 Structured Motion Curve Table

**Profile name:** `structured motion curve table`

**Semantics:** A motion-curve capture table that records keyframe data with
structured interpolation metadata. Each row describes a keyframe or curve
segment with interpolation type, timing, easing, and value data. This is the
most expressive V1 capture profile and the primary target for live-data bake
workflows.

**Required evidence:**

- Each entry records at minimum: a timestamp or frame index, a typed value, and
  interpolation metadata (interpolation type, easing function if applicable).
- Supported interpolation types are explicitly enumerated; unrecognized types
  are rejected.
- The table supports time-range queries: consuming code can request curve
  segments within a time window.
- The table supports serialization to and from graph-owned keyframe patch
  operations that target `clip-param`, `effect-param`, `transition-param`, or
  `shader-uniform` paths.
- Round-trip evidence: serializing a motion curve table to keyframe patches,
  applying them, and reading the result back through the capture table preserves
  the curve within the precision of the interpolation scheme.
- The motion curve table is scoped to a target path owned by a
  graph-authoritative contribution.

**Usable release examples:**

- EX-01 (Clip + Shader + Shader-Uniform Keyframes, M4): shader-uniform
  keyframes that vary over time are stored as structured motion curve table
  entries.
- EX-02 (Effect + Live Data + Bake, M5): this is the primary capture profile
  for baking live data streams (webcam intensity, generated-frame parameters)
  into durable, export-ready motion curves.
- EX-03 (Transition + Agent-Produced Mask Material, M5): transition-param
  automation curves may be recorded as structured motion curve table entries.

**Owning milestone for execution:** M3b (live binding and deterministic capture
execution) after M2 target-path validation.

## 2. Profile Summary

| # | Profile Name | Primary Use | Key Evidence Requirement | Executable After |
|---|---|---|---|---|
| 1 | `seed table` | Reproducible seed-driven outputs | Same seed → same output | M3b |
| 2 | `event table` | Timestamped event sequences with known schemas | Time-range + type-filter queries; conversion gate at M2 | M3b (after M2) |
| 3 | `scalar table` | Single-value parameter/uniform bindings | Lookup by target-path identity + type preservation | M3b |
| 4 | `structured motion curve table` | Keyframe curves with interpolation metadata | Time-range queries + graph-owned keyframe patch round-trip | M3b (after M2) |

## 3. Release Example Cross-Reference

| Release Example | Owning Milestone | Capture Profiles Used |
|---|---|---|
| EX-01 (Clip + Shader + Shader-Uniform Keyframes) | M4 | `scalar table` (static uniforms), `structured motion curve table` (animated uniforms) |
| EX-02 (Effect + Live Data + Bake) | M5 | All four: `seed table`, `event table`, `scalar table`, `structured motion curve table` (primary bake target) |
| EX-03 (Transition + Agent-Produced Mask Material) | M5 | `event table` (agent-session provenance), `structured motion curve table` (transition-param automation) |
| EX-04 (Output Format + Sidecar/Process) | M7b | None directly; sidecar exports may reference capture evidence produced by earlier examples |

## 4. Profile Expansion Gate

**V1 scope is closed.** The four profiles listed in Section 2 are the complete
set of V1 deterministic-capture profiles. Any additional capture profile or
table shape is outside V1 until a later decision record expands scope.

To expand V1 scope, a future milestone must:

1. Provide release-example evidence showing why the existing four profiles are
   insufficient for a concrete graph-backed composed example.
2. Submit a decision record (e.g., an amendment to
   `docs/extensions/composition-spine/m0-decisions.md` Section 7 or a new
   milestone brief) that names the new profile, defines its required evidence,
   assigns it to a release example, and justifies the expansion.
3. Pass the same static-validation grep checks that this document currently
   satisfies: the new profile name must appear only after the decision record is
   accepted, not before.

Until a decision record is accepted, the following candidate concepts are
**explicitly out of V1 scope**:

- **Histogram table** — distribution captures for parameter ranges.
- **Frame-sampled capture** — raw frame-level captures that bypass the
  structured motion curve table interpolation metadata.
- **Audio-amplitude table** — audio analysis captures.
- **Arbitrary binary blob capture** — opaque binary captures without typed
  schema.
- **Multi-dimensional array table** — captures spanning more than one
  structured dimension beyond the four V1 shapes.
- Any capture profile not named `seed table`, `event table`, `scalar table`, or
  `structured motion curve table`.

These candidates remain documented here only as explicit anti-scope markers.
They are not hidden or unlisted; they are listed as excluded. This prevents
ambiguity about whether a missing profile is an oversight or an intentional
deferral.

## 5. Relationship to Other M0 Artifacts

| Artifact | Relationship |
|---|---|
| `README.md` | Indexes this artifact; validation checklist includes a grep check for exactly four V1 profile names |
| `m0-decisions.md` | Section 7 summarizes the four profiles; this document provides the full evidence definitions and release-example assignments |
| `m0-release-examples.md` | EX-01 through EX-04 cite capture profiles in their graph-path assertions and artifact/completion evidence |
| `m0-fixture-matrices.md` | Determinism status rows (`DS-01` through `DS-05`) and blocker rows (`BR-04 live-unbaked`) describe the states that capture profiles resolve |
| `v8-architecture-baseline.md` | Documents the North Star constraint that live/nondeterministic inputs must bake to durable captures before authoritative export |
| `json-rpc-protocol-v0.md` | Process protocol is orthogonal to capture profiles; captures are graph-owned, not process-owned |

## 6. Source Traceability

Every claim in this document traces to stable repo sources:

- `prep.md` line 41: non-media live data bake to deterministic captures.
- `prep.md` line 42: material statuses and detail taxonomy.
- `prep.md` line 76 (Constraints): no expansion of V1 deterministic capture
  beyond selected profiles without release-example evidence.
- `m0-decisions-fixtures.md` Locked Decision line 4: event-table conversion
  gate at M2 validation.
- `m0-decisions-fixtures.md` Locked Decision line 5: first four profiles are
  seed table, event table, scalar table, structured motion curve table.
- `m0-decisions-fixtures.md` Constraints line 3: do not expand V1 capture
  without release-example evidence.
- `m0-decisions-fixtures.md` Scope OUT line 5: no claim that deferred
  capture/profile candidates are in V1 unless a release example requires them.
- `m0-decisions.md` Section 7: V1 capture profile summary.
- `m0-decisions.md` Section 4.1: ownership boundaries for M2 (target-path
  grammar), M3b (keyframe patch semantics), M4 (shader assignment), M5
  (effects/transitions).
- `m0-release-examples.md`: EX-01 through EX-04 graph-path assertions and
  fixture row references.
- `m0-fixture-matrices.md`: `DS-01` through `DS-05` (determinism statuses),
  `BR-04` (live-unbaked blocker).
