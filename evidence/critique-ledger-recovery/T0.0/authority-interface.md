# T0.0 authority-interface

Status: blocked; no owner-issued containment decision was recorded.

## Canonical interface found

The installed source revision is `6787d6363e8fc0603092913ae877db14f3b9fff8`
(`fix/post-c7-release-recovery`). The only matching Run Authority interface is
the read-only Python API:

```python
arnold_pipelines.run_authority.current_source.evaluate_current_source(
    view: RunAuthorityView,
    request: CurrentSourceRequest,
) -> CurrentSourceResult
```

It accepts exact `run_id`, `run_revision`, coordinator attempt, grant, fence,
subject attempt, and decision identities. It returns `SATISFIED` only when the
current revision, active grant, matching coordinator fence, subject attempt,
accepted decision, and quarantine checks all match; otherwise it returns
`DENIED` with a reason. This is authoritative for validating an already-issued
action, not for issuing a containment decision.

## Missing owner capability

No installed owner interface was found that can append or persist a
containment/supersession decision, revoke grants, quarantine a revision, or
return an owner receipt with TTL/termination, revoke/audit path, and CAS
expectation. The typed `Decision` contract permits only `accepted`, `rejected`,
`quarantined`, or `superseded` records supplied to the pure reducer; it does
not provide a writer. The reducer is projection-only. Custody outbox/writer
surfaces are not a Run Authority containment owner and the writer map states
that production gates/effects remain disabled.

Therefore no command/API may safely be invoked for this incident. Shell,
tmux, marker, queue, legacy cloud, or direct-launcher actions are prohibited.
The smallest acceptable follow-up is an accepted Run Authority owner writer
for `RA-CONTAIN` with append-only receipt, exact tuple binding, grant/fence/CAS
checks, deny-all-effects semantics while preserving reads, expiry/termination,
revoke/audit query, and an independent verifier.
