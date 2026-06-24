---
name: megaplan-observe
description: Observe an in-flight megaplan — introspect state, trace events, diagnose blockages, detect drift. Companion to megaplan-prep. Use during and after a run, not before.
---

# Megaplan Observe

When a megaplan is running — or stuck — `megaplan introspect`, `megaplan trace`, and `megaplan doctor` tell you *what it's doing, why, since when, and how to intervene*. This skill covers the observation surface; `megaplan-prep` covers profile/robustness/depth selection before a run.

---

## 1. The four signals

`megaplan introspect --plan X` returns a single structured JSON payload. Four fields in it are the killers — each eliminates a failure mode that previously cost real sessions hours of confusion.

### `now_utc` — the anti-stale-timestamp anchor

Every timestamp in the introspect payload is relative. `now_utc` is the wall clock at the moment the payload was generated. **Never infer recency from JSON timestamps without cross-checking against `now_utc` from the same payload.** A `last_artifact_at` of `14:25:11Z` might look recent — but if `now_utc` is `15:45:00Z`, the artifact is 80 minutes old and the phase is likely stuck.

Rule: when reading introspect output, compute every duration as `now_utc - timestamp`, not as "when I last looked."

### `active_phase.liveness` — the go/no-go enum

One of four values; each dictates a different response:

| Liveness | Meaning | Action |
|---|---|---|
| `progressing` | Events <60s old OR in-flight LLM call exists | Wait. The system is working. |
| `quiet` | Last event 60-300s ago, no in-flight LLM | Watch. May be between checks; check again in 30s. |
| `stalled` | Last event >300s ago AND no unmatched `llm_call_start` | Intervene. The phase has stopped. |
| `timeout-imminent` | Phase age > 80% of `phase_timeout` | Decide now. Extend timeout, kill phase, or accept partial results. |

**Critical rule:** a phase with an unmatched `llm_call_start` (no matching `llm_call_end` yet) is NEVER classified as `stalled`, regardless of wall-clock age. The model is still producing — be patient.

### `block_details.recoverable_via` — the only moves the state machine will accept

When `state: blocked`, this field enumerates the exact recovery actions the state machine will accept. **Never try a recovery action that isn't in this list.** The `invalid_transition` error exists precisely because callers guessed — `recoverable_via` replaces guessing with the canonical transition table.

The list is drawn from `workflow_next()` / `infer_next_steps()` — the single-source function in `megaplan/_core/workflow.py` that the override handler itself checks against. It is always consistent with what `megaplan override` will accept.

### `rubric_doc.drift` — tooling/doc misalignment before it bites

If `rubric_doc.drift.missing_locally` is non-empty, the megaplan-prep skill references profile names your binary doesn't expose. This is the exact failure mode that wastes hours: the skill says `--profile thoughtful`, the binary says `Unknown profile 'thoughtful'`. `drift` catches it before the invocation. Use a profile from `profiles_available_locally` whose recipe matches what the rubric describes, or pin the binary to a state that has the canonical names.

---

## 2. The observation hierarchy

When something seems wrong, investigate in this order:

1. **`megaplan introspect --plan X`** — one call, full picture. Always start here. The four killer fields answer 90% of questions.
2. **`megaplan trace --plan X --follow`** — if introspect says `progressing` but you want to watch. Stream events live; narrative format gives prose summaries of LLM calls.
3. **`megaplan doctor --plan X`** — if introspect shows a flag or state you don't recognise. Diagnostic checks with remediation hints.
4. **Direct filesystem inspection** — last resort. Read `state.json`, `events.ndjson`, phase artifacts manually. If you need this, file a bug — introspect should cover it.

The hierarchy is deliberate: each step is a thin reader over the same `events.ndjson` journal. Jumping to the filesystem before trying the surfaces misses the structured analysis those surfaces provide (liveness computation, drift detection, recoverable_via enumeration).

When a run has a North Star, `introspect` includes an `anchors` summary. Use
`megaplan anchors show --plan X` to inspect the captured anchor text and metadata
before diagnosing drift; prompts use the snapshotted copy, not later edits to the
source `NORTHSTAR.md`.

---

## 3. Failure-mode catalog

Each entry: the `introspect` signature, the recovery, and a worked example from a real session.

### Stalled critique

**Signature:** 4 of N checks complete, `active_phase.last_artifact_rel > 15min`, subprocess still has open network socket, `active_phase.liveness: quiet`.

**Recovery:**
- If `last_artifact_rel < phase_timeout / 2`: wait. The model may be producing a large check artifact.
- If `last_artifact_rel > phase_timeout / 2`: check LLM heartbeat via `trace --follow --format narrative`. If heartbeats stopped, the LLM call may be wedged — kill the phase and resume.
- Check `block_details.outstanding_flags` — if the critique found flags it can't resolve, it may have looped without producing artifacts.

**Worked example:**
> *Session:* `prompt-registry-and-reminder-bundling-v5`, critique phase. 4 of 5 checks completed, last check at 14:25:11Z. At 14:55:00Z, `introspect` shows `liveness: quiet`, `last_artifact_rel: 29m 49s ago`. Subprocess PID 58800 still has an open TCP socket to Fireworks. `trace --follow --format narrative` shows: "Token stream stopped 28m ago. 4,200 tokens emitted at 18 tok/s. Last token at 14:26:31Z — no tokens since." The model finished producing but hermes didn't close the call — likely a provider-side hang. Kill the phase, `megaplan resume` picks up from where critique left off.

### Blocked state

**Signature:** `state: blocked`, `block_details.outstanding_flags` non-empty, `block_details.recoverable_via` populated.

**Recovery:**
1. Read `recoverable_via` — the list is the exact set of override actions the state machine will accept.
2. Pick the first applicable option. If the flags are addressable, fix the brief and re-init. If they're acceptable tradeoffs, `override force-proceed` with a note explaining why.
3. Never paste an override not in the list — it will return `invalid_transition`.

**Worked example:**
> *Session:* Plan went `blocked` at gate with 2 outstanding flags (FLAG-V4-001: high severity invariant contradiction, FLAG-V4-002: medium severity missing coverage). `recoverable_via` shows: `["fix brief and re-init (recommended)", "override add-note + override force-proceed", "override replan (requires state ∈ {critiqued, failed, finalized, gated})"]`. FLAG-V4-001 is a genuine correctness issue — fix the brief to resolve the contradiction, re-init. FLAG-V4-002 is acceptable — the uncovered module is out of scope per the brief. Add a note documenting the scope decision, then `override force-proceed`.

### Rubric/binary drift

**Signature:** `rubric_doc.drift.missing_locally` non-empty. The decision skill references profiles the binary doesn't have.

**Recovery:**
- Use a profile from `profiles_available_locally` whose tier/recipe matches what the rubric describes.
- OR pin the binary to the branch/commit that has the canonical names.
- Run `megaplan doctor --repo` before `megaplan init` to catch this proactively.

**Worked example:**
> *Session:* `megaplan init --profile thoughtful` → `Unknown profile 'thoughtful'`. `introspect` (on a different plan) shows `rubric_doc.drift.missing_locally: ["basic","led","thoughtful","super-premium"]`, `profiles_available_locally: ["solo","directed","partnered","premium","apex"]`. The binary is on branch `sprint-a-base` which renamed the canonical profiles to the new 5-tier scheme. The skill doc hasn't been updated yet. Use `--profile partnered` (the tier-3 equivalent) or switch to main where the old names still exist.

---

## 4. The do-not rules

Four explicit, named rules derived from real failure modes. Violating any of these caused measurable confusion in prior sessions.

### Rule 1: Do not infer wall time from JSON timestamps without `now_utc` cross-check

`state.json` timestamps are snapshot values — they're only as recent as the last write. `now_utc` is the actual wall clock. Always compute recency against `now_utc`. A `last_step.timestamp` of 5 minutes ago might mean the phase is stuck, or it might mean `state.json` hasn't been flushed — `now_utc` tells you which.

### Rule 2: Do not retry overrides that returned `invalid_transition` — read `recoverable_via` first

The state machine rejects invalid transitions with a specific error. Retrying the same override without checking `recoverable_via` is the definition of a loop. `recoverable_via` is computed from the same transition table the handler enforces — it is always correct.

### Rule 3: Do not stash / checkout in the megaplan source repo without user consent — editable installs make repo state load-bearing

If megaplan is installed via `pip install -e .`, any branch switch or uncommitted change in the source tree changes behavior immediately. `megaplan doctor --repo` surfaces this. Stashing, checking out, or pulling without explicit user consent can silently remove the profile a caller is about to invoke.

### Rule 4: Do not assume a phase is stuck before consulting `liveness`

`active_phase.liveness` is the single source of truth for whether a phase is progressing. `progressing` means there's recent activity or an in-flight LLM call — wait. `quiet` means watch. Only `stalled` or `timeout-imminent` warrant intervention. Guessing based on wall-clock intuition leads to killing phases that were about to finish.

---

## 5. Worked invocation chains

### "Is it still going?"

User asks whether a long-running plan is still progressing.

```
megaplan introspect --plan prompt-registry-and-reminder-bundling-v5
```

Read `active_phase.liveness`. If `progressing`: "Yes — critique is still running. Last artifact 3 minutes ago (critique_check_scope.json). Model claude:opus-4.7 is actively producing tokens." If `quiet`: "Critique hasn't produced an artifact in 8 minutes, but the LLM call is still in-flight. Watching." If `stalled`: "Critique appears to have stopped — no events in 12 minutes and no in-flight LLM call. Check `recoverable_via`."

### "Plan went blocked, what now?"

```
megaplan introspect --plan my-sprint
```

Read `block_details.recoverable_via`. Execute the first applicable option. Verify the state transition succeeded with another `introspect` call. If the override was `force-proceed`, confirm `state` is now past `blocked`. If the override was `replan`, confirm the plan re-entered the planning phase.

### "Cost is climbing faster than expected"

```
megaplan trace --plan my-sprint --format narrative --since 10m
```

The narrative format groups consecutive LLM calls into prose summaries. Look for which model is being called, how frequently, and at what token volume. Cross-reference against the tier's expected cost profile from `megaplan-prep`. If the model is correct but call frequency is high, the plan may be looping — check `phase_retry` events. If the model is wrong (e.g., premium model on a solo-tier phase), check for an unintended `override set-profile`.

### "I switched branches and now megaplan is broken"

```
megaplan doctor --repo
```

The repo-level check catches: rubric/binary drift (skill references profiles the current binary doesn't have), editable-install + dirty working tree (uncommitted changes affecting behavior), skill files out of sync with installed copies. Fix the specific WARN/ERROR lines before running any plan.

### "Something's wrong but I don't know what"

```
megaplan introspect --plan X
```

The full payload has the answer. Start at the top:
1. `now_utc` — establish the wall-clock anchor.
2. `active_phase.liveness` — is it progressing?
3. `active_phase.last_artifact_rel` — how long since the last artifact?
4. `block_details` — is it blocked? What flags? What recoveries?
5. `rubric_doc.drift` — is there a profile-name mismatch?
6. `binary_git` — is the binary on the expected branch? Dirty?
7. `timeline` — scan the phase-by-phase breakdown for anomalies.

If nothing jumps out, escalate to `trace --follow` to watch live, then `doctor --plan` for diagnostic checks.
