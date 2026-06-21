# Workflow Manifest Amendment Protocol

The M1 manifest/kernel contract is versioned deliberately. Downstream
milestones must not widen the contract silently.

## Version Bumps

Bump `arnold.workflow.manifest.v1` only when a serialized manifest meaning
changes, a required field is added, a hash input changes, or replay cannot
interpret old events without an alias gate. Additive optional metadata that
does not affect hashes may stay within v1 if validation remains deterministic.

## Proposal Requirements

Every amendment must name:

- The contract field or kernel event family being changed.
- Whether `manifest_hash`, `topology_hash`, or both change.
- How in-flight runs behave: replay with original manifest, replay through an
  explicit compatibility alias, or quarantine with operator-visible rationale.
- Any new volatile golden field and its canonical normalization transform.
- The milestone that owns implementation and the tests proving compatibility.

## Fixture Changes

Behavioral goldens cannot change for import/package-only moves. Legitimate
behavior changes need a sibling `.explanation.md` artifact that names the
behavioral reason and references the milestone.

## Replay Rule

The original manifest reference carried by journaled events is authoritative.
If a newer manifest version cannot resolve a historical event, the resolver
must return an explicit alias or quarantine decision; it must not infer runtime
state from Python object graphs or product package internals.
