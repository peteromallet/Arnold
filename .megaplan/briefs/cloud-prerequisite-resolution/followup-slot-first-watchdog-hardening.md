# M5: Slot-First Watchdog Hardening

## Outcome

Fold the slot-first cloud watchdog runbook and GitHub issue #38 into the chain work so cloud chains keep moving after stops, recoveries, and workspace changes.

## Scope

IN: `extra_repos` and `chain_session` awareness, slot-first worker path selection, `verify-human --list` style discoverability, verification waking chains, provider consistency checks, robust status artifacts, and continuous branch/PR synchronization after stops and recoveries.

OUT: broad provider rewrites or production-only dashboard dependencies.

## Locked Decisions

Branch/PR synchronization is distinct from PR policy and must happen continuously enough that a recovered chain does not leave reviewers or operators looking at stale code. Verification should be able to wake or resume a chain when all prerequisites are already satisfied.

## Done Criteria

The watchdog can identify the right slot/workspace, verify provider/session consistency, surface human-verification options, wake a stopped-but-recoverable chain, and keep branch/PR state fresh after recovery.
