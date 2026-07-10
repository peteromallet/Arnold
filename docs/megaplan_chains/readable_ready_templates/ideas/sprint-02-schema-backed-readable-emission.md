# Sprint 2: Schema-Backed Readable Emission

Implement Sprint 2 from `docs/templates/readable_ready_template_cleanup_plan.md`.

## Branch And Chain Constraints

- Work only on the current shared branch: `main`.
- Do not create, switch to, or push milestone-specific branches.
- Do not add compatibility wrappers, shims, or adapter command paths.
- Preserve unrelated worktree changes. Do not revert files outside this sprint's scope.
- Use `PYENV_VERSION=3.11.11` for local Python commands when needed.

## Goal

Make future generated templates use named outputs and safe widget aliases without
changing semantics.

## Scope

- Add conversion-time provenance-aware schema composition, offline by default.
- Use deterministic schema precedence:
  committed/pinned schema snapshots first, source parser second, provenance-
  matched caches third, local alias fallback fourth, live `/object_info` only
  behind an explicit flag.
- Add opt-in live `/object_info` evidence with provenance.
- Enrich node metadata for output names/types, widget aliases, and schema source.
- Implement named output emission with numeric fallback diagnostics.
- Implement schema-backed widget alias emission with parity guardrails.
- Compare model-like values across original API, regenerated API, requirements,
  workflow requirements, and metadata assets.
- Add readability diagnostics as warnings for avoidable positional outputs,
  unresolved schema-backed widgets, hidden model filenames, and output-name
  ambiguity.

## Success Criteria

- The emitter uses `.out("name")` only when names are unique and safe.
- Schema-backed `widget_N` values are translated where parity proves it.
- Ambiguous output/widget cases remain numeric/positional with diagnostics.
- Representative fixtures compile to equivalent API.
- Stale local caches cannot silently change emitted Python.
