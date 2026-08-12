# G6 Round-11 Gate Receipt — Phase 0B exit GO

Durable, committed record of the G6 oracle round-11 review that closed
Phase 0B (the oracle's raw output previously lived only at
`/tmp/codex_g6_out11.txt`; the T-0101h review flagged that as non-durable
evidence).

## Gate

- **Gate:** G6 — Phase 0B exit (publication boundary)
- **Verdict:** **GO**
- **Verdict quote (round 11):** "safe to commit Phase 0+0B and proceed to
  Phase 1, T-0101 publish/stage/bind/resume"
- **Reviewed scope:** the complete Phase 0B diff (T-0014..T-0027 + G3..G5
  closures) against the six E1–E8 defect classes, default-deny effect gates,
  coherent/current launch+view closure, and T-0027 census refusal on every
  destructive route.

## Reviewed tree

- **Commit reviewed:** `90775c440311dcad83747596abccc48cd1e14ccf` (HEAD at
  review time; the revision under review was uncommitted on top of it)
- **Workdir:** `/Users/peteromalley/Documents/Arnold`

## Exact invocation

The oracle was invoked exactly as:

```
codex exec --sandbox read-only -m gpt-5.6-sol -c model_reasoning_effort=high
```

with the G6 prompt fed via stdin ("Reading additional input from stdin...").

## Run metadata

- **Exit status:** 0
- **Session id:** `019ff51e-cdd4-7421-b34c-94abe653b2d6`
- **Model:** `gpt-5.6-sol` (provider `openai`)
- **Sandbox:** `read-only`; **approval:** `never`; **reasoning effort:** high
- **Started:** 2026-08-12T08:37:44Z; verdict at 2026-08-12T09:02Z

## Output digest

- **Raw output file (review-time path):** `/tmp/codex_g6_out11.txt`
- **SHA-256:** `d0f01b366fedc430c425a469505229cd0118cab5794d62b87a379f55437be2d1`

## Rounds summary (for context)

Rounds 1–10 of G6 closed 13 real defects via fixers N1–N3, O1–O5, P1–P5,
Q1–Q3 (documented in `docs/fixer-recovery-evidence/phase0b-receipts.md`
§3); round 11 was the GO.  Three recurring false positives
(`action_validator.py:331`, the canary promotion-gate blocked property, and
the raw-but-fail-closed reader class) were verified correct and must not be
"fixed".
