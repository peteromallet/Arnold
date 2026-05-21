# Slot-First Cloud Watchdog Runbook

The watchdog should operate from the assigned slot/workspace first, verify provider and session consistency, list available human-verification actions, and only restart or wake chains when the status payload shows the chain is recoverable.

Continuous branch and PR synchronization is required after stops and recoveries so status reflects the code reviewers and operators will actually see.
