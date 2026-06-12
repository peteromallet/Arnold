# Megaplan Chains

This directory holds durable, human-authored planning material for megaplan
runs: chain specs, operator notes, milestone briefs, strategy docs, handoffs,
and review artifacts that should be visible in a normal checkout.

`.megaplan/` is different. It is a mostly gitignored runtime directory for the
megaplan tool: plan execution state, logs, telemetry, wakeup files, local locks,
recovery prompts, and other per-run artifacts. Do not commit generated
`.megaplan/` content.

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
- Never commit `.megaplan/plans/`, `.megaplan/logs/`, `.megaplan/telemetry/`,
  `.megaplan/wakeup/`, `.megaplan/.state-locks/`, or nested `.megaplan/`
  runtime directories.
