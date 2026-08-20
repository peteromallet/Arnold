# Independent T1.8 pass-5 acceptance review

Act as an independent, adversarial, high-reasoning Sol reviewer. This is a
read-only review of source and Git state. The only file you may create or edit is
the result report named below.

Candidate worktree:
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`

Required exact identity:

- commit `06d41e6b7148db4e5b464131762d63fd697db056`
- tree `a8a67b2e01b9129673afdc7931cb3ffdce03a2de`
- subject: bind rollback recovery to authoritative target

Read first:

- `/Users/peteromalley/.codex/attachments/11daeb6c-e3a5-4f8c-8e3b-dd0152840308/pasted-text-1.txt`
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/ACTIVE_STATE_20260802_1712.md`
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass4-sol-result.md`
- `/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-repair-pass4-sol-brief.md`

Verify HEAD/tree/parent and a clean worktree. Inspect the complete candidate
diff. Reproduce the pass-4 blocker adversarially: an owner-signed,
digest-coherent recovery/rollback whose embedded backup or generation belongs
to a different target must fail before any durable intent, selector/store/file/
runtime mutation or effect dispatch. Check initial execution, same-process
replay, response-loss reconciliation, and fresh-process replay. Check that
ordinary valid rollback and forward-fix still work and that verifier/installed
surface semantics agree. Look specifically for target identity being trusted
from caller-controlled recovery payloads, self-consistent wrong-target bundles,
late validation, and receipts that can claim the right target while restoring
another.

Run the smallest fresh hostile probes and targeted suites necessary for an
independent decision. Avoid broad wheel tests while other lanes are active
unless they are indispensable; existing implementer claims are not your proof.

Write a concise, durable `PASS` or `HARD FAIL` report to:
`/Users/peteromalley/Documents/Arnold/.megaplan/subagents/critique-ledger-recovery/T1.8/gen-deploy-independent-review-pass5-sol-result.md`

The report must include exact commit/tree/cleanliness, commands and results,
counterexample outcome, decision, and if failing exactly one bounded blocker.
Do not edit source, Git, cloud, owner, checklist, selector, marker, or sessions.
Return only the verdict, report path, and full-file SHA-256.
