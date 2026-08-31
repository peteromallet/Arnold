# Batch 2 attempt 16 — lifecycle, handler WBC, and native identity proof

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-15 reviews (flag
REWORK for app WBC, regression PASS, contract REWORK for valid roots). The Sol
ruling is explicitly preserved: managed launch retains one canonical WBC and
must not gain a second WBC authority.

- Reopen must validate a complete persisted controlled lifecycle and reject a
  closed-first history before selecting any state.
- The real shared handler must construct one worker WBC internally and reach
  the native door once without a caller-injected WBC.
- Native effort belongs in the selected receipt/spec while route proof remains
  the effort-free canonical route; mismatches and missing native/OMP worker
  identities fail closed without supervisor identity synthesis.

No frozen/index/status/execution-log changes, commit, push, merge, deploy, or
scope expansion.
