# Megaplan Chains

This directory holds durable, human-authored planning material for megaplan
runs: chain specs, operator notes, milestone briefs, strategy docs, handoffs,
and review artifacts that should be visible in a normal checkout.

`.megaplan/` is different. It is a mostly gitignored runtime directory for the
megaplan tool: plan execution state, logs, telemetry, wakeup files, local locks,
recovery prompts, and other per-run artifacts. A small number of legacy files
are force-tracked there today because existing chain specs and historical docs
still reference those paths. Do not bulk-move `.megaplan/` content without
checking those path contracts first.

## Layout

| Path | Purpose |
|---|---|
| `excellence_epic/` | Historical multi-sprint quality epic and handoffs. |
| `loose_work_consolidation_20260612/` | Loose-work consolidation planning from June 12, 2026. |
| `node_resolution_epic/` | Node-resolution epic strategy, chain spec, and test fixtures. |
| `pristine_cleanup/` | Repository cleanup chain, runbook, audits, and results. |
| `readable_ready_templates/` | Ready-template readability chain and cloud/operator notes. |

## Policy

- Put durable planning material that should survive across clones in
  `docs/megaplan_chains/`.
- Leave generated megaplan runtime output in `.megaplan/`.
- Treat `.megaplan/chains/`, `.megaplan/briefs/`, `.megaplan/ideas/`, and
  `.megaplan/tickets/` as legacy/path-sensitive until their references are
  updated or bridged deliberately.
- Never commit `.megaplan/plans/`, `.megaplan/logs/`, `.megaplan/telemetry/`,
  `.megaplan/wakeup/`, `.megaplan/.state-locks/`, or nested `.megaplan/`
  runtime directories.
