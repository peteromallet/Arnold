# Megaplan Documentation

This directory is the working documentation set for Megaplan. Current operator
guidance lives at the top level or in focused subdirectories; historical plans,
sprint briefs, and one-off review artifacts live in `archive/`.

## Start Here

- [Megaplan intro](megaplan-intro.md) - narrative overview of the harness and why it exists.
- [Configuration](configuration.md) - config files, environment variables, and secret sources.
- [Cloud](cloud.md) - cloud orchestration model and command examples.
- [Megaplan prep](megaplan-prep.md) - setup guidance for choosing profile, robustness, and thinking depth.
- [Megaplan epic](megaplan-epic.md) - running multi-sprint epics through `megaplan chain`.
- [Briefs](briefs.md) - committed source docs for single plans and epic chains.

## Core Workflows

- [Pipelines](pipelines.md) - defining pipelines with the Python composition framework.
- [Pipeline architecture](pipeline-architecture.md) - orchestration layer map and extension points.
- [Pipeline resume](pipeline-resume.md) - worked example for stage-based resume cursors.
- [Tickets](tickets.md) - lightweight repo-scoped notes that can be folded into epics.
- [Critique](critique.md) - operational guide for adaptive critique.

## Operations

- [Blocked recovery](ops/blocked-recovery.md) - blocked-run recovery evidence and runbook.
- [Cloud chain smoke](ops/cloud-chain-smoke.md) - cloud chain smoke evidence.
- [Recovery runbooks](ops/recovery-runbooks.md) - recovery flows for local, DB, migration, export, and cloud scenarios.

## Architecture And Design References

- [Canonical vocabulary](canonical-vocabulary.md) - current naming and domain vocabulary map.
- [Characterization gate](characterization-gate.md) - observable behavior freeze for refactor safety.
- [Events](events.md) - event-kind taxonomy for observability.
- [Resolution contract](resolution-contract.md) - disk and memory resolution scoping contract.
- [Skill distribution](skill-distribution.md) - accepted ADR for skill distribution strategy.
- [Hermes vendoring](hermes-vendoring.md) - vendored Hermes validation and git-subtree notes.

## Design Notes And Diagnostics

These are useful technical records, but they are narrower than the operator docs above.

- [Auto-driver / execute boundary diagnosis](auto-execute-boundary-diagnosis.md)
- [Epic adversarial review](epic-adversarial-review.md)
- [Epic vetting philosophy](epic-vetting-philosophy.md)
- [Execute token aggregation](execute-token-aggregation.md)
- [Observability and introspection design](observability-and-introspection-design.md)
- [Silent failure census](silent-failure-census.md)

## Audits, Archive, And Assets

- [Foundation audit](foundation-audit/FOUNDATION_PREAMBLE.md) - entry point for the subsystem audit packet.
- [Archive](archive/README.md) - historical migrations, generated plans, sprint notes, and stale one-off artifacts.
- [Assets](assets/) - images used by docs and reports.
