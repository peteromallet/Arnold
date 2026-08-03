# Finalize response-contract relaunch preflight

This is the admission gate for the first Finalize dispatch after the Attempt 9
response-contract failure. It is intentionally a pre-dispatch checklist: old
live output must not be promoted or repaired after the fact.

## Root failure and fixed invariant

The Finalize prompt asked for `requires_human_only_reason`, but the model-owned
schema did not declare or require it. When the first response failed semantic
validation, the repair reused the primary `-o` path and could be prompted from
Codex JSONL transport rather than the exact selected response. That destroyed
the primary evidence and made repair provenance ambiguous.

The fixed contract now requires every `user_actions[]` item to contain exactly
the canonical human-only reason field and a canonical phase. Each primary and
repair dispatch has a distinct output path. The selected `-o` response must be
non-empty and, when assistant messages are present in JSONL, equal to the last
message (earlier progress messages before tool calls are valid). Transport and
selected response are stored as hash-addressed evidence with the plan, phase,
invocation, phase-WBC attempt, worker-WBC attempt, occurrence, and repair
ordinal. A semantic repair receives the full
selected object—including the authenticated candidate rather than its receipt
when artifact handoff is used—the full canonical schema, and the actual
structural-audit failure.

## Required pre-dispatch checks

1. Deploy one runtime commit containing the schema, selection, evidence, and
   handoff changes together. Record the exact commit and tree in chain and
   cloud-session custody before dispatch.
2. Confirm the plan is `gated`, has no `active_step`, and has no live Finalize
   process. Confirm the worker-dispatch and phase WBC ledgers have no new
   attempt after the terminal Attempt 9 row.
3. Confirm `MEGAPLAN_TRUSTED_CONTAINER=1` is explicitly supplied by the
   trusted outer container. Do not infer this from hostname, Docker presence,
   UID, or a writable filesystem.
4. Run the ordinary Finalize command once. Before Codex starts, the runtime
   must pass the atomic non-empty artifact-handoff canary in the exact plan
   filesystem. A canary failure is terminal pre-dispatch evidence and must not
   consume a model attempt.
5. Observe exactly one new phase-WBC and worker-WBC attempt. Do not retry from
   shell automation. If the primary response fails, only the built-in repair
   ordinal 1 may run, and its `-o` path must differ from ordinal 0.
6. Before accepting success, inspect
   `.megaplan/model-response-evidence/occurrences/<occurrence>/repair-*.json`.
   Each receipt must bind the live plan/invocation/WBC IDs, have non-zero
   selected-output bytes, and hash to the referenced immutable object. If a
   JSONL assistant message exists, selection must be `accepted` and equal to
   the last assistant message.
7. Accept Finalize only if the new WBC is `COMPLETED`, the canonical
   `finalize.json` passes handler validation, state is `finalized`, and the next
   step is `execute`. A timeout, stall, non-zero Codex exit, empty output,
   mismatch or exhausted repair remains terminal; never salvage a
   partial live artifact post hoc.

## Focused verification

Run:

```text
python -m pytest tests/orchestration/test_provider_response_contract.py tests/orchestration/test_codex_output_schema.py -q
```

The regression corpus includes the Attempt 9 legacy user-action shape, exact
missing-field repair, primary/repair non-overwrite, response selection
empty/last-message mismatch rejection, intermediate-message tolerance,
hash-addressed WBC binding, zero-byte
receipt rejection, and the trusted-container filesystem canary.
