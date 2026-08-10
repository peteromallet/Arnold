# Sprint 1 — Step receipts + scope-drift hardening

## Goal

Introduce per-phase **step receipts** (structured, auditable records), promote **scope-drift** to a first-class metric that can block in hardened robustness levels, and expose the receipts through a new `megaplan audit query` subcommand. This is the foundation layer that a future multi-profile bake-off feature will ride on.

## Why

Across recent runs we discovered that executor models sometimes invent unrequested code (e.g., glm-5.1 at execute phase added a `_sandbox_fingerprint` helper and `sandbox_hash` field in SessionInfo that no task asked for — caught only by an advisory audit finding, not blocked). We have no structured way to:

1. Compare how different models perform at the same phase across runs.
2. Ask longitudinal questions like "how often does glm produce scope drift at execute?"
3. Replay the *exact same* prompt through a different model to isolate model effects from plan-drift confounds.

Existing data is scattered across `state.history`, per-phase artifacts (`plan_v1.md`, `critique_v1.json`, `execution.json`, `review_output.json`), and hermes session logs at `~/.hermes/sessions/session_<id>.json`. A denormalized append-only projection shaped for querying fixes all three questions with one primitive.

## Scope

### 1. Canonical prompt hash (load-bearing primitive)

Every receipt records both:
- `prompt_hash_raw` — sha256 of the full rendered prompt (exact debugging).
- `prompt_hash_canonical` — sha256 after redacting a fixed allow-list of transient fields (timestamps, plan-id, absolute repo paths, env fingerprints). Canonicalization function lives in `megaplan/receipts/canonical.py` and is version-controlled (`canonicalization_version: 1`).

Tests must prove two runs of the same plan at the same phase produce identical `prompt_hash_canonical` values. This is the contract everything else depends on; get it right before shipping anything else.

### 2. Step receipt schema (v1)

One receipt per `(plan_id, phase, iteration, attempt)`. Written as `step_receipt_<phase>_v<iteration>.json` inside the plan directory **and** appended as a single JSON line to a global `~/.megaplan/audit/receipts.jsonl` (plan-dir copy wins if they diverge; jsonl is rebuildable from plan dirs).

Schema tiers:

**Identity & provenance**
- `receipt_id` (uuid), `plan_id`, `phase`, `iteration`, `attempt`
- `timestamp_utc`, `profile_name`, `agent`, `agent_mode` (`oneshot` | `persistent`)
- `model_configured` (what the profile asked for)
- `model_actual` (what the hermes session actually answered — these diverge)
- `session_id`, `megaplan_version` (git sha), `schema_version`

**Input identity**
- `prompt_hash_raw`, `prompt_hash_canonical`, `canonicalization_version`
- `upstream_artifact_hashes` (ordered list; e.g. critique's upstream is the plan_v1.md hash; execute's upstream is finalize.json hash)

**Mechanical metrics**
- `cost_usd`, `duration_ms`, `prompt_tokens`, `completion_tokens`
- `verdict` (phase-overloaded: `approved` / `needs_rework` / `proceed` / etc.)
- `metrics` (phase-specific object, below)

### 3. Phase-specific metric extractors

Pure functions in `megaplan/receipts/extractors.py` — take already-written artifacts as input, return metrics dicts, no I/O. Trivially testable; can backfill historical plans.

- **Plan**: `step_count`, `task_count`, `files_referenced`, `oos_file_count`, `plan_chars`, `plan_words`, `success_criteria_count`, `must_vs_info_ratio`, `structure_warnings_count`.
- **Critique**: `findings_per_check` (map), `severity_distribution`, `clean_checks_count`, `flagged_checks_count`, `rubber_stamp_ratio`.
- **Gate**: `recommendation`, `blocking_flags_resolved`, `blocking_flags_remaining`, `override_forced`.
- **Finalize**: `tasks_count`, `sense_checks_count`, `per_task_evidence_file_count`.
- **Execute**: `files_claimed`, `files_in_diff`, `scope_drift_files_added`, `scope_drift_files_missing`, `loc_added`, `loc_removed`, `loc_added_outside_claimed`, `commands_run_count`, `advisory_issues_count`, `blocking_issues_count`.
- **Review**: `review_verdict`, `task_verdicts_count` / `total_tasks`, `sense_check_verdicts_count` / `total`, `missing_evidence_count`, `rework_items_count`, `criteria_pass_count`, `criteria_deferred_count`.

Called from each handler immediately before `_finish_step` in `megaplan/handlers/shared.py`, alongside the existing `make_history_entry` call.

### 4. Scope-drift as first-class metric (behavior change)

Formula:
```
scope_drift_files_added   = |files_in_diff \ files_claimed \ benign_set|
scope_drift_files_missing = |files_claimed  \ files_in_diff|
loc_added_outside_claimed = LOC in files_in_diff but not in files_claimed
```

`benign_set` is a single constant allow-list: `.megaplan/**`, `execution.json`, `final.md`, `review.json`, `*.meta.json`, lock files.

`scope_drift_severity`:
- `none` — zero drift
- `low` — `files_added > 0` OR `loc_added_outside_claimed <= 20`
- `high` — `files_added > 0 AND loc_added_outside_claimed > 20`

Surfacing:
1. Top-of-StepResponse summary for execute when drift ≠ none (loud, unambiguous).
2. `scope_drift_severity` as a first-class field on the receipt.
3. **Blocking promotion** in `megaplan/execute/quality.py`: `standard` robustness still advises, but `robust` and `superrobust` hard-block on `high` severity. This is the directly-actionable change that would have caught the recent glm regression.

### 5. Global audit log + query subcommand

Location: `~/.megaplan/audit/receipts.jsonl` (append-only, fsynced). Optional per-repo mirror at `<repo>/.megaplan/audit/receipts.jsonl` for repo-self-containment; home-dir is authoritative for cross-repo longitudinal queries.

New subcommand `megaplan audit query`:
- `--model <name>` / `--phase <name>` / `--profile <name>` / `--since <duration>`
- `--agg avg,p50,p95` (aggregations over cost, duration, scope-drift-severity)
- Outputs a table to stdout, or `--json` for structured output.

Keep the jsonl queryable via `jq` as a fallback — do not invent a binary format. An optional `receipts.index.sqlite` rebuilt on demand from the jsonl is fine as a cache, but the jsonl is source of truth.

### 6. Out of scope (explicit)

- **Qualitative / LLM-judge evaluation** — shipped in a later sprint. This sprint is mechanical-only.
- **Isolated-phase replay** (`megaplan replay`) — enabled by the canonical hash landed here, but built later.
- **Bake-off / multi-profile runs** — Sprint 2.
- **Blob store for archived inputs** — v1 relies on plan-dir bytes being available; a content-addressed blob store is v2.

## Success criteria

1. Every phase writes a `step_receipt_<phase>_v<iter>.json` and appends to the global jsonl.
2. A test proves `prompt_hash_canonical` is stable across two runs of the same plan-phase.
3. `megaplan audit query --model glm-5.1 --phase execute` returns a table with at least duration, cost, scope_drift_severity per historical run.
4. Scope drift with `high` severity blocks execute at robustness `robust` (tested with a fixture where the executor intentionally modifies an unclaimed file).
5. Existing plans continue to function — receipts are additive, never replacing or breaking current artifacts.
6. No behavior change at `standard` robustness beyond receipt emission and advisory scope-drift messaging.
