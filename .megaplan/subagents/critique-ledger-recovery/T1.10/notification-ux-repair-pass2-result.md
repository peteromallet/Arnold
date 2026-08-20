PASS candidate repair

Commit: `109d2a38bf6da210f650d5bf480967a19d9a09a8`

Implemented sealed owner-authority/root admission, stable lineage and replay
identity, single-active CAS-fenced provider claims, typed provider receipts,
validated provenance-only recipients, monotonic exact-version authority state,
ledger/outbox/provider reduction, malformed-input durable identity, payload and
receipt allowlists, progress-auditor/webhook quarantine, and the fail-closed
canonical notification worker wrapper. Added adversarial regressions.

Verification:

- Focused notification/diagnostic/ledger suites: `72 passed`.
- Watchdog wrapper suite: `408 passed`; the five diagnostic cases exposed in
  that combined run were repaired and rerun: `5 passed`.
- Reviewer probes: two-process/200-observation admission and claim races,
  pending-attempt fanout rejection, authority/root/test-seal isolation,
  rotation replay, pseudo-recipient custody routing, deleted/corrupt-row
  reducer rebuild, malformed gate identity, secret exclusion, arbitrary
  provider mapping, typed success, provider crash/response-loss, and ENOSPC.
- `py_compile`, `bash -n`, and `git diff --check` passed.
- Wheel build/install/import and materialized-wrapper parity passed; the new
  worker wrapper exits 78 without installed owner/provider configuration.

Remaining external integration limits: this candidate has no installed owner
RA/Custody/WBC resolver or real provider adapter, so real signed provider
receipts and owner reconciliation require deployment integration. The
canonical worker fails closed until those are installed.

No cloud, SSH, Discord, deployment, or provider effect was performed: all
provider calls in probes were local fakes, and the production resolver/worker
had no installed authority or provider configuration. This is only a candidate
for fresh independent Luna review; formal T1.10 completion is not claimed.
