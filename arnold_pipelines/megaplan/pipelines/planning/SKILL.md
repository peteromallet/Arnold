> **Authority status (M11):** Zero-authority history. All repair, audit, and deployment authority has been migrated to canonical delegation. This document is retained for reference only — it must not be used to materialize commands, grant authority, or drive automated actions.

# Planning Pipeline — Skill Reference

## Overview

The `megaplan` pipeline (packaged at `megaplan/pipelines/planning/`) is the built-in megaplan plan-production substrate.
Its canonical registry identity is `megaplan` with the legacy alias `planning → megaplan`.
It orchestrates the full prepare → plan → critique/gate/revise loop →
finalize → execute → review lifecycle.

---

## Gate verdict vocabulary

The gate stage emits a `PipelineVerdict` whose `recommendation` field is one
of the following `GateRecommendation` literals:

| Verdict | Meaning |
|---|---|
| `proceed` | Gate approved the plan; advance to finalize (and optionally execute). |
| `iterate` | Gate rejected the plan; re-enter the critique → revise loop. |
| `tiebreaker` | Evaluators are split; hand off to the tiebreaker stage for adjudication. |
| `escalate` | Quality ceiling reached at current tier; escalate to a higher-complexity model. |

---

## Robustness levels

Robustness controls the depth of the critique/gate loop and the number of
evaluators engaged. Canonical names (accepted by `--robustness` / config):

| Level | Alias(es) | Behaviour |
|---|---|---|
| `bare` | `tiny` | Single-pass, no gate loop. Fastest; for quick drafts. |
| `light` | — | One critique + revise round, minimal gate criteria. |
| `full` | `standard` | Standard gate loop (default). Balanced quality/cost. |
| `thorough` | `robust` | Extended gate loop, stricter criteria, more evaluators. |
| `extreme` | `superrobust` | Maximum depth, all evaluators enabled. |

The default robustness when no `--robustness` flag is supplied is `full`.

---

## Stage topology

```
prep → plan → critique ──→ gate ──proceed──→ finalize [→ execute → review]
                 ↑             │
                 └──iterate────┘
                               │
                               └──tiebreaker──→ [adjudication] → finalize
```

Driver substrate: `subprocess_isolated` (execute/review) + `graph+loop-node`
(critique→gate→revise subloop).

`arnold_api_version`: `1.0`
`capabilities`: `plan, execute, review`
