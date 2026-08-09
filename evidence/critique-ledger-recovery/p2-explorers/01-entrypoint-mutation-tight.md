# Luna explorer 1b — tight entry-point authority check

You are GPT-5.6 Luna, read-only, high reasoning. Do not use collaboration
tools, do not edit files, and do not run cloud commands. Inspect no more than
these files: `arnold_pipelines/megaplan/cloud/cli.py`,
`arnold_pipelines/megaplan/cloud/providers/ssh.py`,
`arnold_pipelines/megaplan/agentbox_adapter.py`,
`arnold_pipelines/megaplan/blocker_recovery.py`, and
`arnold_pipelines/megaplan/handlers/override.py`. Do not recurse into wrapper
generated text or the whole repository.

Sol's P2 proposal is a versioned ExecutionAttempt ledger and one admission
controller. Answer only: (1) exact launch/state/recovery bypasses visible in
these files, (2) which current checks are advisory rather than authoritative,
(3) the smallest admission boundary and fields needed, and (4) four concrete
tests. Cite file and line references. Return under 900 words and stop.
