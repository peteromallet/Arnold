# Luna review brief — Batch 3 NBF-04 attempt 2

Review the cumulative NBF-04 candidate at checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. Bind the review to the Batch 3
execution brief SHA `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`,
attempt-1 packet SHA `b1d84fc21d6dbf56e47c6813373eb1f1476c1b4ba5ba532ec1da66d58d3fed59`,
attempt-1 review brief SHA `cf0bf486da547414b2fa11e68fcc52795df39faed304b838765560b81cdf9835`,
and the frozen plan/tasklist/North Star/goal/custody hashes recorded in the
attempt-2 packet.

Judge NBF-04 only. Confirm the canonical ladder is record-before-signal,
TERM then distinct KILL confirmation, same-incarnation/PID-reuse protection,
already-dead handling, exactly-once disposition/terminal append, and replay
without resignal. Confirm ledger projection/reconciliation and ControlledFinalLaunch
do not invent or bypass history. Confirm native, managed, launcher, fan,
resident, operator, orphan, and timeout paths route real worker actions through
the single existing disposition/WBC authority, with strict missing context and
no raw worker signal/fallback. Confirm child certification reuses the existing
WBC attempt and does not create another admission authority.

Use the exact attempt-2 validation and baseline/environment exceptions in
`.oracle/rework/batch-3-nbf04-attempt-2.md`. Do not expand into NBF-05/06,
generated inventory redesign, status/execution-log edits, frozen artifacts,
commit/push/merge/deploy, or unrelated fixture cleanup. Treat the full
tracked+untracked source/test diff hash
`140104caf75bb6aa1137b0df35c7dc434986ff6efe00f71a33ac584f55ba45d7` and path
manifest hash
`b785c2e5f048614f05f5462430ea22905e867c8300e1bca324aa04854857320d` as the
reviewed candidate inputs.
