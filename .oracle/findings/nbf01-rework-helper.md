# NBF-01 rework implementation-assistance checklist

> Status: implementation assistance only. This is not an Oracle review,
> acceptance decision, or full-suite result. No source or test files were
> edited by this helper.

## Bound identities

- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Rework tasklist `.oracle/rework/batch-1-attempt-1.md`:
  `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c`
- Frozen tasklist is `.oracle/tasklist.md`; its NBF-01 contract and exact
  required test names were used as the authority for this checklist.
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Candidate snapshot inspected: `922241d0bdb3e993c3b554cc69f19948adef7bc3`

## RW-01 — locked read/compare/append and reservation binding

The named mutation methods currently enter the existing sequence-sidecar lock,
but the following semantic checks remain mechanical holes to close:

- `IncidentLedger.reserve`: a supplied `changed_precondition_event_id` is
  checked for existence/consumed state, but reservation does not emit a
  `changed_precondition_consumed` record or validate the event's plan, phase,
  subject, terminal ordering, and provider-key binding. The reservation field
  does mark the event consumed in replay, so implementation must preserve one
  atomic single-use path rather than create a second journal.
- `IncidentLedger.consume_changed_precondition`: a fabricated valid
  `ChangedPrecondition` whose ID is absent from projection can currently cause
  a consumed marker to be appended. Require the referenced event to be
  persisted and compare the supplied object with the persisted payload.
- `IncidentLedger.append_terminal_outcome`: derive the expected admission
  receipt from the committed reservation event and compare it; compare the
  physical door; do not skip `logical_dispatch_id` for provider exhaustion;
  bind accepted-launch marker, worker/process identity, timing, and execution
  context to the reservation. The current reservation has no receipt field,
  so checking only `reservation.get("admission_receipt_id")` is vacuous.
- `IncidentLedger.reconcile_reservation`: a nonempty
  `evidence_event_ids`/`evidence_kind=controlled_adapter` is not proof of a
  persisted receipt-bound `not_started` marker. Require positive persisted
  sequencing evidence and reject contradictory entered/accepted/terminal
  evidence. Check prior identical reconciliation before rejecting a closed
  target, so exact replay is idempotent.
- `IncidentLedger.reserve_provider_route_child`: authorizer existence is now
  checked, but authorization is not consumed atomically and multiple distinct
  child IDs can reuse one recovery event. Bind parent plan/phase/projection/
  logical identity and require unresolved/no-launch parents to fail.
- `IncidentLedger._project_records` / `read_nbf_events`: replay accepts any
  parsed `incident.nbf.*` payload without validating the stored schema. Invalid
  JSON objects can therefore affect projection or raise. Invalid records must
  fail closed and never project.

Suggested exact tests:

- `test_two_process_reservation_contention_one_winner`
- `test_two_process_terminal_linkage_is_atomic`
- `test_terminal_rejects_reservation_context_mismatch`
- `test_terminal_requires_persisted_accepted_launch_context`
- `test_blind_release_and_accepted_launch_release_reject`
- `test_recovered_disposition_links_existing_record_without_duplicate`
- `test_conflicting_reconciliation_rejected_identical_replay_idempotent`
- `test_crash_after_read_before_append_exposes_no_partial_reservation`
- `test_lock_schema_and_projection_version_mismatch_fail_closed`
- `test_consumed_change_cannot_authorize_second_reservation`
- `test_recovery_authorization_single_use_across_different_children`
- `test_invalid_replay_record_never_projects`

The contention cases should use separate OS processes and a real ledger
directory, not only sequential calls or in-process mocks.

## RW-02 — strict schema and illegal-state matrix

- `ChangedPrecondition.__post_init__` does not enforce the fixed
  reason-to-producer-kind/version mapping when callers instantiate the class
  directly; append/decode must not provide a constructor bypass.
- `validate_nbf_event` checks only a subset of terminal payload constraints.
  Worker identity/timing, canonical provider evidence/key, and accepted launch
  context need equivalent append-path validation, not decode-only coverage.
- `SupervisionConfirmation.from_dict` does not recompute `confirmation_id`,
  validate an ISO first timestamp, or require finite expiry consistent with the
  configured TTL.

Required behavioral tests to retain/add:

- `test_dispatch_outcome_incompatible_payload_matrix`
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_oom_rejects_falsey_or_negative_cgroup_evidence`
- `test_unknown_death_rejects_fabricated_killer_and_signal`
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`

Each relevant schema case needs an append-path variant through
`IncidentLedger._append_nbf`/`validate_nbf_event`.

## RW-03 — authoritative changed-precondition producers

- `ChangedPrecondition.produce` is still a generic `**kwargs` entry point. It
  allows caller-supplied reason-specific authoritative fields and provider
  keys instead of reading canonical before/after sources and cited evidence.
- `IncidentLedger.append_changed_precondition` accepts a fabricated but
  well-formed event without resolving its evidence event or validating derived
  content IDs/provider-key transitions.
- `ChangedPrecondition.__post_init__` now checks the event-ID formula, but
  event ID/content IDs/evidence digest are still not bound to authoritative
  ledger evidence.
- `IncidentLedger.consume_changed_precondition` needs persisted-event identity
  comparison in addition to the locked consumed check (see RW-01).

Suggested exact tests:

- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_consumed_change_cannot_authorize_second_reservation`

The forged-ID test must use valid 64-hex values that differ from the digest of
the authoritative fixture; malformed-length-only coverage is insufficient.

## RW-04 — keyed provider replay mechanics

- `IncidentLedger._project_records` stream identity includes plan/phase/current
  selected spec/chain/key, but omits the required `primary_spec`; terminal
  payloads do not reliably carry configured fallback-chain identity.
- A different-key exhaustion creates a new stream but leaves the old stream's
  streak intact; `max(observation_streak)` can report the stale key at streak 2
  instead of the new active key at streak 1. Active state should follow the
  canonical event/key stream, not the largest historical count.
- Success and ordinary-failure/worker-disposition handling currently operates
  over all streams sharing the same base, rather than the applicable keyed
  stream. Success must reset only the applicable key; an intervening ordinary
  failure/disposition must break that stream without entering degradation.
- Changed-precondition events are not projected into provider-stream reset or
  rekey behavior. Only an authoritative before/after provider-key change may
  do so; a key-unchanged change must preserve observations.
- `reserve_provider_route_child` checks an authorizer but does not consume it,
  allowing one `provider_recovery_verified` event to authorize distinct child
  reservations. Probe/recovery must preserve the existing streak while
  authorizing exactly one linked same-route child.
- Provider failure keys/evidence are not canonically validated before entering
  the reducer.

Suggested exact tests:

- `test_provider_streak_is_keyed_not_global`
- `test_nonmatching_key_rekeys_at_one`
- `test_success_resets_only_applicable_key`
- `test_probe_and_recovery_preserve_streak_and_authorize_one_child`
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
- `test_disposition_breaks_consecutiveness_without_degradation`

## RW-05 — durable confirmation identity/replacement/expiry and CLI

- `IncidentLedger.observe_confirmation` only appends an observed event; there
  is no durable replacement/expiry state machine. PID, process-start,
  progress, cause, and supervisor/container-incarnation changes need a
  replacement event and a new first scan.
- `SupervisionConfirmation` and `validate_nbf_event` do not recompute the
  confirmation identity. Direct `ledger.observe_confirmation` can therefore
  accept a forged ID.
- `IncidentLedger.observe_confirmation` validates only first evidence digest
  and timing for consumption. It does not compare all second-scan identity
  fields; `disposition.consume_confirmation` makes those equality arguments
  optional, allowing omission of the proof.
- First observation needs duplicate/reopen behavior that preserves the
  original expiry; repeated same-identity observations must not silently
  overwrite the original first scan. Expired/replaced events must be durable
  and replayed under the existing ledger lock.
- `_record_cli` checks confirmation status before full disposition schema
  validation, so malformed worker payloads can return status 5 instead of 2.
  It validates only confirmation reference consumption, not that the submitted
  disposition's receipt/PID/start/progress/incarnation/cause context matches
  the consumed confirmation. Sustained-proof non-worker dispositions also need
  the required confirmation rule where applicable.
- CLI status 4 is reachable for an existing file path, but constructor/path
  validation should remain fail-closed for unavailable/non-ledger locations
  without collapsing into status 3. Status 3 requires an append/lock fault
  fixture.

Suggested exact tests:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_expired_mismatched_and_already_consumed_confirmation`

## Current test inventory note

At inspection time the eight named NBF-01 test modules contained only small
smoke tests; the required contention, append-path, forged-authority,
key-isolation, replacement/expiry, and CLI branch names above were absent.
This note is a gap checklist for the executor, not a statement about any later
unseen edits.
