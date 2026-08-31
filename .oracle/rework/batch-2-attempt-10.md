# Batch 2 attempt 10 — constructor authority correction

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-9 brief SHA
`33ea754ee09e18d07a6cabe03cabc5cbcf63b5cb08ab96a86e72cac492b28bd9` and the
independent Luna constructor-design finding; no additional Sol oracle was
commissioned.

- **A10-REMOVE-SEAM** — production admission has no caller-supplied native
  constructor seam or capability; the canonical gate owns backend preparation.
  A non-production seam remains isolated for unit coverage.
- **A10-DOOR-IMMUTABLE** — native and OMP doors derive physical door, selected
  route, and authorization from canonical inputs; managed derives model from
  its immutable command spec.
- **A10-MANAGED-PRE** — running receipt emission occurs only after managed
  admission succeeds.
- **A10-REALTEST** — focused admission/terminal/lifecycle and handler tests
  preserve zero-pre-admission side-effect and exactly-once contracts where
  available.

No second WBC authority, frozen/status/execution-log/index changes, commit,
push, merge, deploy, or Batch-3 redesign.
