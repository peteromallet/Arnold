# T4.4 reconcile old v2 GLEKs — Luna preparation

Verdict: **NO RECONCILIATION; preparation only.**

## Exact universe

Derive the universe from authoritative WBC ledgers joined to T0.4, T4.1 quarantine, T4.2 RA revoke and T4.3 Custody tombstone/epoch—not logs or notifications. Include every v2 parent/child GLEK, occurrence/attempt, request/idempotency/provider ID, intent/start/response/receipt, RA revision/fence, Custody lease/epoch, runtime generation and effect target. Effect classes: Discord/channel/DM/chunks, webhook/HTTP, Git/push/PR, model request, cloud/SSH/deploy/service, publication, notification, fixer/diagnostic/launch and any generic subprocess/native effect. Reject duplicate, missing-parent, orphan-child, reused-key, unknown-class or cross-tuple rows as unresolved.

## Reconciliation matrix

| Durable WBC + independent provider/owner observation | Outcome |
|---|---|
| No start and provider proves absence | `NOT_APPLIED` terminal; no send |
| Accepted receipt, exact identity/payload/target | `APPLIED` terminal; adopt only |
| Explicit provider rejection before application | `FAILED` terminal; no retry under retired tuple |
| Start/dispatch persisted, acknowledgement missing or provider unavailable | `INDETERMINATE` unresolved, permanently no-redispatchable |
| Provider says applied but local ack lost, exact identity matches | adopt `APPLIED_AFTER_RECONCILIATION` with provider evidence |
| Conflicting/mixed/late identity, partial chunks, unknown target | `INDETERMINATE_CONFLICT`, unresolved/no-redispatch |

`UNKNOWN` means owner/provider observation itself is unavailable or cannot establish which world occurred. `FAILED` requires affirmative non-application/rejection evidence; timeout, disconnect, crash, lost response, missing row or absence of acknowledgement is never FAILED.

## Transaction and late receipts

Freeze exact universe digest, then claim each GLEK once under current RA deny fence and T4.3 epoch. Read WBC intent/start/receipt plus provider observation through registered read-only adapters. CAS append one outcome; never rewrite history. Parent terminalizes only when every child has a compatible terminal outcome; any indeterminate child keeps parent unresolved. A late authentic receipt may monotonically resolve INDETERMINATE to applied/rejected only if exact provider/request/payload/target/child identity matches and owner policy permits adoption. Conflicting late receipts append conflict and remain unresolved. No new provider call is allowed.

## No-redispatch proof

For every unresolved/terminal old GLEK, exercise direct dispatcher, retry worker, restart, fixer, watchdog, notification chunker, model fallback, Git wrapper, installed/source/editable/direct-import/container paths. All must reject before provider invocation because RA is revoked, Custody target is tombstoned/advanced, and WBC key is terminal or `no_redispatch=true`. Runtime spies plus provider query establish zero calls across two observers and 200 scans.

## Races and faults

Test two reconcilers; late receipt before/during/after CAS; provider observation response loss; partial multi-chunk apply; parent/child completion race; wrong provider ID; payload/target digest substitution; reused idempotency key; stale RA fence/Custody epoch; database/WAL corruption; ENOSPC before outcome commit; process crash at every read/CAS; provider applied then unavailable; provider rejection after misleading timeout; forged absence; restored old WBC snapshot; new retry scheduler. Exactly one canonical append/adoption occurs; ambiguity never becomes failure or redispatch.

## Receipt and independent observation

Emit signed WBC receipt binding universe/source digests, exact tuple, RA/T4.2 and Custody/T4.3 heads, ordered per-GLEK evidence/outcome, parent-child graph, provider-observer identities/query windows/raw digests, unresolved set, no-redispatch flags, CAS/WAL proof, signer/key/revocation head and result. Independent verifier uses separate read-only WBC/provider channels, recomputes every join/count, probes zero calls and confirms projections preserve unresolved ambiguity.

Current execution is blocked by T4.1–T4.3 and absent accepted owner/provider observation interfaces. No code, Git, cloud, provider, process, owner or checklist state was mutated. This report is the sole write; SHA-256 is external.
