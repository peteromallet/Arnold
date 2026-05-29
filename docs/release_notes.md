# Release Notes

Release notes live under [`docs/release_notes/`](release_notes/).

- [v2.8.0](release_notes/v2.8.0.md) — seams, IR purity, and contract foundation (controlled breaking minor under 2.x).
- [v2.7.0](release_notes/v2.7.0.md) — documentation reconciliation and public API surface alignment.

## v2.7 Sprint 1 Foundation

- Runtime schema degradation is loud by default. If object_info schema validation is unavailable, VibeComfy logs an ERROR listing skipped class types and records them in run metadata as `schema_validation_skipped`.
- Temporary off-ramp: pass `--quiet-schema-degradation` on `vibecomfy run` or set `VIBECOMFY_SCHEMA_WARN_ONLY=1` to downgrade the log to WARNING while migrating existing monitors.
